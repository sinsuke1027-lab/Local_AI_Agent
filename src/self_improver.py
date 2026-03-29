"""self_improver.py - P10a: 自己改善エージェント 分析基盤 + 改善提案生成"""

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TASK_HISTORY_DB   = Path.home() / ".roo" / "task_history.db"
LESSONS_JSON      = Path(__file__).parent.parent / "lessons.json"
DISCORD_WEBHOOK   = "http://localhost:5678/webhook/discord-send"


# ── データクラス ────────────────────────────────────────────

@dataclass
class ModelStats:
    model: str
    total: int
    success: int
    failed: int
    success_rate: float       # 0.0-1.0
    avg_tokens: float
    avg_cost: float


@dataclass
class ErrorPattern:
    pattern: str              # 例外クラス名 or 先頭50文字
    count: int
    examples: list[str]       # エラーメッセージのサンプル（最大3件）
    affected_tasks: list[str] # task_idリスト


@dataclass
class ComplexityStats:
    score: int                # 1-10
    total: int
    success: int
    success_rate: float
    debate_triggered: int
    debate_revision: int      # NEEDS_REVISIONの回数


@dataclass
class AnalysisReport:
    period_days: int
    total_tasks: int
    overall_success_rate: float
    model_stats: list[ModelStats]
    error_patterns: list[ErrorPattern]
    complexity_stats: list[ComplexityStats]
    lessons_count: int
    generated_at: str


@dataclass
class Suggestion:
    category: str   # "model" / "prompt" / "routing" / "constitution" / "process"
    priority: str   # "high" / "medium" / "low"
    title: str
    description: str
    action: str


# ── メインクラス ────────────────────────────────────────────

class SelfImprover:
    """タスク履歴を分析し、改善提案を生成する。"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or TASK_HISTORY_DB

    # ------------------------------------------------------------------
    # 内部: SQLiteユーティリティ
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _since_iso(self, days: int) -> str:
        return (datetime.now() - timedelta(days=days)).isoformat()

    # ------------------------------------------------------------------
    # 内部: 分析メソッド
    # ------------------------------------------------------------------

    def _analyze_models(self, conn: sqlite3.Connection, since: str) -> list[ModelStats]:
        rows = conn.execute("""
            SELECT
                model_used,
                COUNT(*) as total,
                SUM(CASE WHEN error_message IS NULL THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN error_message IS NOT NULL THEN 1 ELSE 0 END) as failed,
                AVG(COALESCE(token_count, 0)) as avg_tokens,
                AVG(COALESCE(cost_estimate, 0)) as avg_cost
            FROM tasks
            WHERE completed_at >= ? AND model_used IS NOT NULL
            GROUP BY model_used
            ORDER BY total DESC
        """, (since,)).fetchall()

        stats = []
        for r in rows:
            total = r["total"] or 1
            stats.append(ModelStats(
                model=r["model_used"],
                total=r["total"],
                success=r["success"],
                failed=r["failed"],
                success_rate=r["success"] / total,
                avg_tokens=r["avg_tokens"] or 0.0,
                avg_cost=r["avg_cost"] or 0.0,
            ))
        return stats

    def _extract_error_type(self, error_message: str) -> str:
        """エラーメッセージから例外クラス名を抽出する。"""
        match = re.match(r"^(\w*(?:Error|Exception|Warning|Timeout))", error_message or "")
        if match:
            return match.group(1)
        return (error_message or "")[:50].strip()

    def _analyze_errors(self, conn: sqlite3.Connection, since: str) -> list[ErrorPattern]:
        rows = conn.execute("""
            SELECT task_id, error_message
            FROM tasks
            WHERE completed_at >= ? AND error_message IS NOT NULL
        """, (since,)).fetchall()

        groups: dict[str, dict] = {}
        for r in rows:
            key = self._extract_error_type(r["error_message"])
            if key not in groups:
                groups[key] = {"count": 0, "examples": [], "tasks": []}
            groups[key]["count"] += 1
            if len(groups[key]["examples"]) < 3:
                groups[key]["examples"].append(r["error_message"])
            groups[key]["tasks"].append(r["task_id"])

        patterns = [
            ErrorPattern(
                pattern=k,
                count=v["count"],
                examples=v["examples"],
                affected_tasks=v["tasks"],
            )
            for k, v in groups.items()
        ]
        patterns.sort(key=lambda p: p.count, reverse=True)
        return patterns

    def _analyze_complexity(self, conn: sqlite3.Connection, since: str) -> list[ComplexityStats]:
        rows = conn.execute("""
            SELECT
                complexity_score,
                COUNT(*) as total,
                SUM(CASE WHEN error_message IS NULL THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN debate_triggered = 1 THEN 1 ELSE 0 END) as debate_count,
                SUM(CASE WHEN debate_result LIKE '%NEEDS_REVISION%' THEN 1 ELSE 0 END) as debate_revision
            FROM tasks
            WHERE completed_at >= ? AND complexity_score IS NOT NULL
            GROUP BY complexity_score
            ORDER BY complexity_score
        """, (since,)).fetchall()

        stats = []
        for r in rows:
            total = r["total"] or 1
            stats.append(ComplexityStats(
                score=r["complexity_score"],
                total=r["total"],
                success=r["success"],
                success_rate=r["success"] / total,
                debate_triggered=r["debate_count"],
                debate_revision=r["debate_revision"],
            ))
        return stats

    def _count_lessons(self) -> int:
        try:
            data = json.loads(LESSONS_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return len(data.get("lessons", []))
            return len(data) if isinstance(data, list) else 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # 公開API
    # ------------------------------------------------------------------

    def analyze(self, days: int = 7) -> AnalysisReport:
        """指定期間のタスク履歴を分析し、AnalysisReportを返す。"""
        since = self._since_iso(days)

        if not self.db_path.exists():
            logger.warning("task_history.db not found: %s", self.db_path)
            return AnalysisReport(
                period_days=days, total_tasks=0, overall_success_rate=0.0,
                model_stats=[], error_patterns=[], complexity_stats=[],
                lessons_count=self._count_lessons(),
                generated_at=datetime.now().isoformat(),
            )

        conn = self._connect()
        try:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN error_message IS NULL THEN 1 ELSE 0 END) as success
                FROM tasks WHERE completed_at >= ?
            """, (since,)).fetchone()

            total = row["total"] or 0
            success = row["success"] or 0
            overall_rate = (success / total) if total > 0 else 0.0

            return AnalysisReport(
                period_days=days,
                total_tasks=total,
                overall_success_rate=overall_rate,
                model_stats=self._analyze_models(conn, since),
                error_patterns=self._analyze_errors(conn, since),
                complexity_stats=self._analyze_complexity(conn, since),
                lessons_count=self._count_lessons(),
                generated_at=datetime.now().isoformat(),
            )
        finally:
            conn.close()

    def generate_suggestions(self, report: AnalysisReport) -> list[Suggestion]:
        """分析結果からルールベースの改善提案を生成する。"""
        suggestions: list[Suggestion] = []

        # ルール1: モデル別成功率が低い
        for ms in report.model_stats:
            if ms.total >= 5 and ms.success_rate < 0.8:
                suggestions.append(Suggestion(
                    category="model",
                    priority="high",
                    title=f"{ms.model}の成功率が低下（{ms.success_rate*100:.0f}%）",
                    description=f"{ms.total}タスク中{ms.failed}件失敗。",
                    action=(
                        f"{ms.model}の失敗タスクを確認し、"
                        "別モデルへの切替またはプロンプト改善を検討"
                    ),
                ))

        # ルール2: エラーパターンが繰り返されている
        for ep in report.error_patterns:
            if ep.count >= 3:
                suggestions.append(Suggestion(
                    category="prompt",
                    priority="high",
                    title=f"{ep.pattern}が{ep.count}回発生",
                    description=f"影響タスク: {', '.join(ep.affected_tasks[:3])}",
                    action=(
                        f"coder_agentのプロンプトに「{ep.pattern}に注意」の指示を追加、"
                        "またはlessons.jsonに教訓を追加"
                    ),
                ))
            elif ep.count >= 2:
                suggestions.append(Suggestion(
                    category="prompt",
                    priority="medium",
                    title=f"{ep.pattern}が{ep.count}回発生",
                    description=f"影響タスク: {', '.join(ep.affected_tasks[:3])}",
                    action="エラーパターンを監視し、再発時にプロンプト改善を検討",
                ))

        # ルール3: 高複雑度タスクの成功率が低い
        for cs in report.complexity_stats:
            if cs.score >= 7 and cs.total >= 3 and cs.success_rate < 0.7:
                suggestions.append(Suggestion(
                    category="process",
                    priority="high",
                    title=f"高複雑度タスク（score={cs.score}）の成功率が低下（{cs.success_rate*100:.0f}%）",
                    description=f"{cs.total}タスク中{cs.total - cs.success}件失敗。",
                    action=(
                        "debate_thresholdを下げる（現在7→5に変更検討）、"
                        "またはタスク分割を促すプロンプト改善"
                    ),
                ))

        # ルール4: ディベートのNEEDS_REVISION率が高い
        total_debate = sum(cs.debate_triggered for cs in report.complexity_stats)
        total_revision = sum(cs.debate_revision for cs in report.complexity_stats)
        if total_debate >= 3 and total_revision / total_debate > 0.7:
            suggestions.append(Suggestion(
                category="prompt",
                priority="medium",
                title=f"ディベートNEEDS_REVISION率が高い（{total_revision}/{total_debate}）",
                description="coder_agentの初回生成品質に改善余地がある可能性",
                action="coder_agentのプロンプトに品質チェックリストを追加",
            ))

        # ルール5: lessonsが少なく成功率が低い
        if report.lessons_count < 5 and report.overall_success_rate < 0.9:
            suggestions.append(Suggestion(
                category="process",
                priority="low",
                title="教訓（lessons.json）が少ない",
                description=f"現在{report.lessons_count}件。失敗パターンの蓄積が不十分",
                action=(
                    "extract_and_save_lesson()の動作を確認し、"
                    "失敗時の自動教訓抽出が正常に動いているか検証"
                ),
            ))

        # 優先度順ソート
        order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: order.get(s.priority, 9))
        return suggestions

    def format_report(
        self,
        report: AnalysisReport,
        suggestions: list[Suggestion],
    ) -> str:
        """マークダウン形式のレポートを生成する。"""
        lines: list[str] = []
        lines += [
            f"# 🔍 自己改善分析レポート（直近{report.period_days}日間）",
            f"生成日時: {report.generated_at}",
            "",
            "## 概要",
            f"- 総タスク数: {report.total_tasks}",
            f"- 全体成功率: {report.overall_success_rate*100:.1f}%",
            f"- 蓄積教訓数: {report.lessons_count}",
            "",
        ]

        # モデル別
        if report.model_stats:
            lines.append("## モデル別パフォーマンス")
            for ms in report.model_stats:
                lines += [
                    f"### {ms.model}",
                    f"- タスク数: {ms.total}（成功{ms.success} / 失敗{ms.failed}）",
                    f"- 成功率: {ms.success_rate*100:.1f}%",
                    f"- 平均トークン: {ms.avg_tokens:.0f}",
                    f"- 平均コスト: ${ms.avg_cost:.4f}",
                    "",
                ]

        # エラーパターン
        if report.error_patterns:
            lines.append("## エラーパターン")
            for ep in report.error_patterns:
                lines.append(f"### {ep.pattern}（{ep.count}回）")
                for ex in ep.examples[:2]:
                    lines.append(f"- {ex[:100]}")
                lines.append("")

        # 複雑度別
        if report.complexity_stats:
            lines.append("## 複雑度別分析")
            for cs in report.complexity_stats:
                debate_info = (
                    f"ディベート{cs.debate_triggered}回"
                    if cs.debate_triggered else "ディベートなし"
                )
                lines.append(
                    f"- score={cs.score}: {cs.total}件"
                    f"（成功率{cs.success_rate*100:.0f}%、{debate_info}）"
                )
            lines.append("")

        # 改善提案
        if suggestions:
            lines.append("## 💡 改善提案")
            emoji_map = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            for i, s in enumerate(suggestions, 1):
                emoji = emoji_map.get(s.priority, "⚪")
                lines += [
                    f"### {emoji} {i}. {s.title}",
                    f"- カテゴリ: {s.category}",
                    f"- {s.description}",
                    f"- **アクション**: {s.action}",
                    "",
                ]
        else:
            lines += [
                "## ✅ 改善提案なし",
                "現在の運用に大きな問題は検出されませんでした。",
            ]

        return "\n".join(lines)

    def notify_suggestions(self, suggestions: list[Suggestion]) -> bool:
        """改善提案をDiscord（n8n Webhook経由）に通知する。"""
        if not suggestions:
            return True

        emoji_map = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        text = "🔍 **自己改善エージェント: 改善提案**\n\n"
        for i, s in enumerate(suggestions, 1):
            emoji = emoji_map.get(s.priority, "⚪")
            text += f"{emoji} **{i}. {s.title}**\n"
            text += f"  アクション: {s.action}\n\n"
        text += "上記の提案を確認してください。適用する場合はClaude Codeで実行してください。"

        try:
            httpx.post(
                DISCORD_WEBHOOK,
                json={"content": text},
                timeout=10.0,
            )
            logger.info("Sent %d suggestions to Discord", len(suggestions))
            return True
        except Exception as e:
            logger.warning("Failed to notify suggestions: %s", e)
            return False

    def run(self, days: int = 7) -> str:
        """analyze → generate_suggestions → format_report を一括実行。"""
        report = self.analyze(days=days)
        suggestions = self.generate_suggestions(report)
        return self.format_report(report, suggestions)


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Self Improvement Analyzer")
    parser.add_argument("--days", type=int, default=7, help="Analysis period in days")
    parser.add_argument("--notify", action="store_true", help="Send suggestions to Discord")
    args = parser.parse_args()

    improver = SelfImprover()
    print(improver.run(days=args.days))

    if args.notify:
        report = improver.analyze(days=args.days)
        suggestions = improver.generate_suggestions(report)
        improver.notify_suggestions(suggestions)
