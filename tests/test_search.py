from src.task_history_indexer import TaskHistoryIndexer
idx = TaskHistoryIndexer()
res = idx.search_similar_tasks("Pythonで1から10までの合計を計算する関数を書いて")
for r in res:
    print(r['distance'], r['metadata']['instruction'][:20] if 'instruction' in r['metadata'] else r['metadata'].get("task_id"))
