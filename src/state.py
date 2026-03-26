from typing import TypedDict, Optional, List
from datetime import datetime


class TaskState(TypedDict):
    # 基本情報
    task_id:        str
    instruction:    str
    input_mode:     str        # text / handwriting / voice
    template_id:    Optional[str]
    project_id:     Optional[str]

    # 実行情報
    model_used:     Optional[str]
    token_count:    Optional[int]
    cost_estimate:  Optional[float]
    started_at:     Optional[str]
    completed_at:   Optional[str]

    # 品質情報
    quality_score:  Optional[float]
    test_pass_rate: Optional[float]
    lint_errors:    Optional[int]
    retry_count:    Optional[int]

    # 成果物情報
    changed_files:  Optional[List[str]]
    diff_summary:   Optional[str]
    report_url:     Optional[str]
    pr_url:         Optional[str]

    # ファイル操作フラグ
    needs_file_operation: Optional[bool]

    # 内部制御
    next_node:      Optional[str]
    error_message:  Optional[str]
    result:         Optional[str]
    channel_id:     Optional[str]
    requester:      Optional[str]