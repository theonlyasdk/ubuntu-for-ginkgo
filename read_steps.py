import json

with open(r'C:\Users\User\.gemini\antigravity-cli\brain\21a6c850-2347-4a10-a680-53523d7da634\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        idx = obj.get('step_index', 0)
        if 2727 <= idx <= 2760:
            print(f"STEP {idx}: {obj.get('type')}")
            if 'tool_calls' in obj:
                for tc in obj['tool_calls']:
                    print(f"  TC: {tc.get('name')}({tc.get('args')})")
            if 'content' in obj and obj['content']:
                print(f"  Content: {repr(obj['content'][:250])}")
