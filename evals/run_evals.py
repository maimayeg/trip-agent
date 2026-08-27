# evals/run_eval.py
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

from agent import agent, get_tools_called   # reuse what you already built
from prompts.system import SYSTEM_PROMPT
from evals.dataset import EVAL_CASES

judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
langfuse_handler = CallbackHandler()

JUDGE_PROMPT = """You are grading a trip-planning assistant's answer.

Question: {question}
Answer: {answer}

Score the answer from 1-5 on each dimension:
- accuracy: is the information correct and non-hallucinated?
- completeness: does it actually address what was asked?
- helpfulness: would a traveler find this useful and clear?

Respond with ONLY valid JSON, no markdown fences, in this exact shape:
{{"accuracy": <int>, "completeness": <int>, "helpfulness": <int>, "reasoning": "<one sentence>"}}
"""

def run_agent(question: str) -> dict:
    response = agent.invoke(
        {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}
            ]
        },
        config={"callbacks": [langfuse_handler]}
    )
    answer = response["messages"][-1].content
    tools_called = get_tools_called(response["messages"])
    return {"answer": answer, "tools_called": tools_called}

def judge(question: str, answer: str) -> dict:
    prompt = JUDGE_PROMPT.format(question=question, answer=answer)
    result = judge_llm.invoke(prompt)
    text = result.content.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"accuracy": None, "completeness": None, "helpfulness": None,
                "reasoning": f"JUDGE PARSE FAILED: {text[:200]}"}

def main():
    results = []
    for case in EVAL_CASES:
        print(f"Running: {case['question'][:60]}...")
        try:
            agent_out = run_agent(case["question"])
            scores = judge(case["question"], agent_out["answer"])
            results.append({
                "question": case["question"],
                "category": case["category"],
                "answer": agent_out["answer"],
                "tools_called": agent_out["tools_called"],
                **scores,
            })
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({
                "question": case["question"],
                "category": case["category"],
                "answer": None,
                "tools_called": [],
                "accuracy": None, "completeness": None, "helpfulness": None,
                "reasoning": f"RUN FAILED: {e}",
            })
    os.makedirs("evals/results", exist_ok=True)
    out_path = f"evals/results/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} results to {out_path}\n")
    print_summary(results)

def print_summary(results):
    dims = ["accuracy", "completeness", "helpfulness"]
    for dim in dims:
        scored = [r[dim] for r in results if r[dim] is not None]
        avg = sum(scored) / len(scored) if scored else 0
        print(f"{dim:>12}: avg {avg:.2f}  ({len(scored)}/{len(results)} scored)")

    print("\nLowest-scoring cases:")
    ranked = sorted(
        (r for r in results if r["accuracy"] is not None),
        key=lambda r: r["accuracy"] + r["completeness"] + r["helpfulness"]
    )
    for r in ranked[:3]:
        print(f"  [{r['category']}] {r['question'][:60]}")
        print(f"    scores: acc={r['accuracy']} comp={r['completeness']} help={r['helpfulness']}")
        print(f"    reason: {r['reasoning']}")

if __name__ == "__main__":
    main()