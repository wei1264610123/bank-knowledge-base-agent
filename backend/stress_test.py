"""
压测脚本 - 模拟多用户并发全链路问答（登录 -> 建会话 -> 流式问答）

用法示例:
  默认3用户并发、每用户2次问答:
    python stress_test.py

  指定并发与次数（会真实调用阿里云百炼LLM，注意API额度/限流）:
    python stress_test.py --users 5 --requests 3

  使用已有账号（不注册新用户）:
    python stress_test.py --users 4 --username admin --password 123456

输出: 成功率、TPS、首token延迟与总耗时(毫秒)的 P50/P90/P95/P99
"""
import argparse
import asyncio
import json
import random
import statistics
import time
import uuid
from dataclasses import dataclass, field

import httpx

# 默认题库（银行业务问题）
DEFAULT_QUESTIONS = [
    "如何办理信用卡？",
    "转账限额是多少？",
    "如何修改登录密码？",
    "如何开通网上银行？",
    "定期存款的利率是多少？",
]

# 密码强度需满足后端规则
TEST_PASSWORD = "Stress#123456"


@dataclass
class UserResult:
    """单个用户的压测结果"""
    username: str
    first_token_times: list = field(default_factory=list)   # 首token耗时(ms)
    total_times: list = field(default_factory=list)         # 全量耗时(ms)
    content_chars: list = field(default_factory=list)       # 回复字数
    errors: list = field(default_factory=list)              # (阶段, 错误信息)


async def login(client: httpx.AsyncClient, base: str, username: str, password: str) -> str:
    """登录获取token，失败抛异常"""
    resp = await client.post(
        f"{base}/auth/login",
        data={"username": username, "password": password},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"登录失败({resp.status_code}): {resp.text[:200]}")
    return resp.json()["access_token"]


async def register_user(client: httpx.AsyncClient, base: str) -> tuple:
    """注册并登录一个新用户，返回 (username, token)"""
    username = f"stress_{uuid.uuid4().hex[:10]}"
    email = f"{username}@stress.com"
    resp = await client.post(
        f"{base}/auth/register",
        json={"username": username, "email": email, "password": TEST_PASSWORD},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"注册失败({resp.status_code}): {resp.text[:200]}")
    token = await login(client, base, username, TEST_PASSWORD)
    return username, token


async def create_session(client: httpx.AsyncClient, base: str, token: str) -> str:
    """创建新会话，返回session_id"""
    resp = await client.post(
        f"{base}/chat/sessions",
        json={"title": "压测会话"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"创建会话失败({resp.status_code}): {resp.text[:200]}")
    return resp.json()["id"]


async def stream_chat(
    client: httpx.AsyncClient, base: str, token: str, session_id: str, question: str
) -> dict:
    """
    发送流式问答，返回统计信息。
    - first_ms: 首token耗时(毫秒, 流结束或异常时记为总耗时)
    - total_ms: 从发起到收到done的耗时(毫秒)
    - chars:    回复总字符数
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"session_id": session_id, "message": question, "stream": True}

    start = time.perf_counter()
    first_ms = None
    chars = 0
    finished = False

    async with client.stream(
        "POST", f"{base}/chat/completions", json=payload, headers=headers, timeout=300
    ) as resp:
        if resp.status_code != 200:
            body = await resp.aread()
            raise RuntimeError(f"问答接口HTTP {resp.status_code}: {body.decode('utf-8', errors='ignore')[:200]}")

        buffer = ""
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            dtype = data.get("type")
            if dtype == "content":
                chunk = data.get("content", "")
                chars += len(chunk)
                if first_ms is None:
                    first_ms = (time.perf_counter() - start) * 1000
            elif dtype == "done":
                finished = True
                break
            elif dtype == "error":
                raise RuntimeError(f"服务端错误: {data.get('message', '未知')[:200]}")

    total_ms = (time.perf_counter() - start) * 1000
    return {
        "first_ms": first_ms if first_ms is not None else total_ms,
        "total_ms": total_ms,
        "chars": chars,
        "finished": finished,
    }


async def run_user(
    base: str,
    username: str,
    password: str,
    requests: int,
    questions: list,
    result: UserResult,
    local_only: bool = False,
) -> None:
    """单个用户的完整压测流程（串行发requests次请求，模拟真人）"""
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            token = await login(client, base, username, password)

            if local_only:
                # 本地模式：只压 建会话 + 拉历史（不消耗LLM额度）
                session_id = await create_session(client, base, token)
                for i in range(requests):
                    try:
                        start = time.perf_counter()
                        resp = await client.get(
                            f"{base}/chat/sessions/{session_id}/messages",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=30,
                        )
                        total_ms = (time.perf_counter() - start) * 1000
                        if resp.status_code != 200:
                            raise RuntimeError(f"历史接口HTTP {resp.status_code}: {resp.text[:200]}")
                        result.first_token_times.append(total_ms)
                        result.total_times.append(total_ms)
                        result.content_chars.append(len(resp.text))
                    except Exception as e:
                        result.errors.append((f"历史#{i + 1}", str(e)))
                return

            session_id = await create_session(client, base, token)

            for i in range(requests):
                question = questions[i % len(questions)]
                try:
                    stat = await stream_chat(client, base, token, session_id, question)
                    result.first_token_times.append(stat["first_ms"])
                    result.total_times.append(stat["total_ms"])
                    result.content_chars.append(stat["chars"])
                except Exception as e:
                    result.errors.append((f"问答#{i + 1}", str(e)))
    except Exception as e:
        result.errors.append(("初始化", str(e)))


def percentile(data: list, p: float) -> float:
    """计算分位数"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * p
    lower = int(idx)
    upper = min(lower + 1, len(sorted_data) - 1)
    if lower == upper:
        return sorted_data[lower]
    return sorted_data[lower] + (sorted_data[upper] - sorted_data[lower]) * (idx - lower)


def print_summary(users: list, start: float, walltime: float, total_requests: int, total_success: int) -> None:
    """汇总并打印压测报告"""
    all_first = []
    all_total = []
    all_chars = []
    errors = []

    for u in users:
        all_first.extend(u.first_token_times)
        all_total.extend(u.total_times)
        all_chars.extend(u.content_chars)
        errors.extend(u.errors)

    success_rate = (total_success / total_requests * 100) if total_requests else 0.0
    qps = (len(all_total) / walltime) if walltime > 0 else 0.0

    def fmt(v: float) -> str:
        return f"{v:.0f}"

    print("\n" + "=" * 60)
    print("STRESS TEST REPORT")
    print("=" * 60)
    print(f"Total wall time       : {walltime:.1f}s")
    print(f"Concurrent users      : {len(users)}")
    print(f"Total requests        : {total_requests}")
    print(f"Completed (success)   : {total_success}")
    print(f"Failed                : {total_requests - total_success}")
    print(f"Success rate          : {success_rate:.1f}%")
    print(f"Throughput (QPS)      : {qps:.2f}")
    print("-" * 60)
    print(f"First-token latency (ms)  P50={fmt(percentile(all_first, 0.5))}  "
          f"P90={fmt(percentile(all_first, 0.9))}  "
          f"P95={fmt(percentile(all_first, 0.95))}  "
          f"P99={fmt(percentile(all_first, 0.99))}")
    print(f"Total latency (ms)        P50={fmt(percentile(all_total, 0.5))}  "
          f"P90={fmt(percentile(all_total, 0.9))}  "
          f"P95={fmt(percentile(all_total, 0.95))}  "
          f"P99={fmt(percentile(all_total, 0.99))}")
    print(f"Avg reply length       : {statistics.mean(all_chars) if all_chars else 0:.0f} chars")
    print("-" * 60)
    if errors:
        print("Error detail:")
        counter = {}
        for stage, msg in errors:
            key = msg[:120]
            counter[key] = counter.get(key, 0) + 1
        for msg, count in list(counter.items())[:10]:
            print(f"  [{count}x] {msg}")
    else:
        print("No errors.")
    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="银行客服RAG系统 全链路并发压测")
    parser.add_argument("--base-url", default="http://localhost:8000/api", help="后端API地址")
    parser.add_argument("--users", type=int, default=3, help="并发用户数(默认3)")
    parser.add_argument("--requests", type=int, default=2, help="每用户问答次数(默认2)")
    parser.add_argument("--username", default="", help="使用已有账号(不注册); 与--password配合")
    parser.add_argument("--password", default="", help="已有账号密码")
    parser.add_argument("--questions", default="", help="自定义问题列表(逗号分隔)")
    parser.add_argument("--local-only", action="store_true",
                        help="仅压本地接口(登录/建会话/拉历史)，不调用LLM，不消耗额度")
    args = parser.parse_args()

    questions = [q.strip() for q in args.questions.split(",") if q.strip()] or DEFAULT_QUESTIONS

    mode = "LOCAL (no LLM)" if args.local_only else "FULL CHAIN (real LLM)"
    print(f"Target: {args.base_url}")
    print(f"Mode  : {mode}")
    print(f"Concurrent users: {args.users}, requests per user: {args.requests}")
    print(f"Questions pool: {len(questions)} items")
    if not args.local_only:
        print("NOTE: This performs REAL LLM calls via Alibaba Bailian (consumes quota).")
    print("Proceeding...\n")

    async with httpx.AsyncClient(trust_env=False, timeout=30) as http:
        # 健康检查
        try:
            resp = await http.get(f"{args.base_url}/auth/me", timeout=10)
            if resp.status_code == 401:
                print("[OK] backend reachable")
            else:
                print(f"[WARN] /auth/me returned {resp.status_code}")
        except Exception as e:
            print(f"[ERROR] Backend unreachable: {e}")
            print("Please start the backend first: python run.py")
            return

    results = [UserResult(username="") for _ in range(args.users)]
    total_requests = args.users * args.requests
    start = time.perf_counter()

    async with httpx.AsyncClient(trust_env=False) as http:
        # 每个用户预注册/登录（注册失败的用户跳过，不再发空账号请求）
        accounts = []
        for i in range(args.users):
            if args.username:
                accounts.append((args.username, args.password))
                results[i].username = args.username
            else:
                try:
                    username, _ = await register_user(http, args.base_url)
                    accounts.append((username, TEST_PASSWORD))
                    results[i].username = username
                    print(f"  registered user: {username}")
                except Exception as e:
                    results[i].errors.append(("注册", str(e)))
                    accounts.append(None)  # 标记该用户不可用

        # 并发执行用户任务（每个用户串行发requests次）
        tasks = [
            asyncio.create_task(
                run_user(args.base_url, *accounts[i], args.requests, questions, results[i], args.local_only)
            )
            for i in range(args.users)
            if accounts[i] is not None
        ]
        if not tasks:
            print("[ERROR] No valid accounts, abort.")
            return
        for coro in tasks:
            await coro

    walltime = time.perf_counter() - start
    total_success = sum(len(r.first_token_times) for r in results)
    print_summary(results, start, walltime, total_requests, total_success)


if __name__ == "__main__":
    asyncio.run(main())