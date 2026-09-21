"""
聊天服务 - RAG核心实现（直接调用阿里云百炼兼容接口）
"""
import json
import asyncio
from typing import List, AsyncGenerator
import httpx

from app.config import settings
from app.models.chat import ChatMessage
from app.database import async_session_factory
from app.services.rag_service import RAGService


class ChatService:
    """聊天服务"""

    # 最大重试次数
    MAX_RETRIES = 3

    def __init__(self):
        self.rag_service = RAGService()
        self.base_url = settings.OPENAI_API_BASE
        self.api_key = settings.DASHSCOPE_API_KEY
        self.model = settings.LLM_MODEL

    def _build_system_prompt(self, context: str) -> str:
        """构建系统提示词"""
        return f"""你是一个专业的银行客服助手，名叫"小银"。

## 角色定位
- 你是银行的智能客服，专门回答用户关于银行业务的问题
- 你的回答必须基于提供的知识库内容，确保准确性和专业性
- 如果知识库中没有相关信息，请诚实地告知用户，并建议联系人工客服

## 回答规范
1. 回答要准确、专业、简洁、友好
2. 使用中文回答
3. 在回答中标注引用来源，格式：[来源: 文档名称]
4. 如果问题不清晰，请礼貌地要求用户澄清
5. 涉及敏感操作（如转账、密码修改）时，提醒用户注意安全

## 知识库内容
{context}
"""

    def _build_messages(self, message: str, history: List[ChatMessage], context: str) -> List[dict]:
        """构建消息列表"""
        messages = [{"role": "system", "content": self._build_system_prompt(context)}]

        # 添加历史消息（只保留最近10轮，避免请求过大）
        for msg in history[-20:]:
            messages.append({
                "role": "user" if msg.role == "user" else "assistant",
                "content": msg.content
            })

        # 添加当前问题
        messages.append({"role": "user", "content": message})
        return messages

    def _get_client(self) -> httpx.AsyncClient:
        """创建HTTP客户端（禁用系统代理，避免DNS干扰）
        注意：httpx 0.28+ 的 AsyncHTTPTransport 不再接受 connect_timeout/read_timeout，
        超时统一在 AsyncClient 的 timeout 参数中设置。
        """
        transport = httpx.AsyncHTTPTransport(
            retries=1  # 传输层重试
        )
        return httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(connect=30, read=180, write=60, pool=30),
            trust_env=False  # 忽略系统代理设置
        )

    async def get_response(
        self,
        message: str,
        history: List[ChatMessage],
        session_id: str
    ) -> dict:
        """获取AI回复（非流式）。
        使用独立的短生命周期 session 保存AI消息，避免持有长事务连接。
        """
        # 检索相关文档
        docs = await self.rag_service.retrieve_documents(message)
        context = "\n\n".join([doc.page_content for doc in docs]) if docs else "暂无相关知识库内容"
        references = self.rag_service.format_references(docs)

        # 构建消息
        messages = self._build_messages(message, history, context)

        # 调用API（带重试）
        response = await self._call_api(messages)

        # 保存AI回复（独立session，立即提交，不依赖请求生命周期）
        async with async_session_factory() as save_db:
            ai_message = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=response,
                references=references
            )
            save_db.add(ai_message)
            await save_db.commit()

        return {
            "content": response,
            "references": references
        }

    async def _call_api(self, messages: List[dict]) -> str:
        """调用阿里云百炼对话API（非流式，带重试）"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": False
        }

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with self._get_client() as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code != 200:
                        raise Exception(f"API错误: {response.status_code} - {response.text}")

                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except (httpx.HTTPError, Exception) as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    wait = attempt * 2  # 递增等待: 2s, 4s
                    print(f"API调用失败(第{attempt}次): {e}，{wait}秒后重试...")
                    await asyncio.sleep(wait)

        raise Exception(f"API调用失败({self.MAX_RETRIES}次重试后): {last_error}")

    async def stream_chat(
        self,
        message: str,
        history: List[ChatMessage],
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """流式获取AI回复。
        AI消息使用独立session保存，流式响应期间不占用请求级数据库连接。
        """
        # 检索相关文档
        docs = await self.rag_service.retrieve_documents(message)
        context = "\n\n".join([doc.page_content for doc in docs]) if docs else "暂无相关知识库内容"
        references = self.rag_service.format_references(docs)

        # 构建消息
        messages = self._build_messages(message, history, context)

        full_response = ""

        try:
            # 调用API（流式，带重试）
            async for chunk in self._stream_api(messages):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                await asyncio.sleep(0)

            # 发送引用来源
            yield f"data: {json.dumps({'type': 'references', 'references': references})}\n\n"

            # 发送完成信号
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

            # 保存AI回复（独立session，立即提交）
            async with async_session_factory() as save_db:
                ai_message = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    references=references
                )
                save_db.add(ai_message)
                await save_db.commit()

        except Exception as e:
            print(f"流式对话失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            # 补充完成信号，避免客户端一直等待结束标记
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    async def _stream_api(self, messages: List[dict]) -> AsyncGenerator[str, None]:
        """调用阿里云百炼对话API（流式，带重试）"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": True
        }

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with self._get_client() as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            body = await response.aread()
                            raise Exception(f"API错误: {response.status_code} - {body.decode('utf-8', errors='ignore')}")
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    return
                                try:
                                    data = json.loads(data_str)
                                    delta = data["choices"][0]["delta"]
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except (json.JSONDecodeError, KeyError, IndexError):
                                    continue
                return  # 成功完成
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    wait = attempt * 2
                    print(f"流式API失败(第{attempt}次): {e}，{wait}秒后重试...")
                    await asyncio.sleep(wait)

        raise Exception(f"流式API调用失败({self.MAX_RETRIES}次重试后): {last_error}")