import unittest
from pathlib import Path

from src.utils.exceptions import ParseError, UnsupportedFileError
from src.utils.models import AIResult, FileJob, ParseResult
from src.workflow.results import build_result_record, resolve_record_status


class BuildResultRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.job = FileJob(
            job_id="job-001",
            file_path=Path("data/inbox/example.txt"),
            file_name="example.txt",
            extension=".txt",
        )
        self.parse_result = ParseResult(
            file_name="example.txt",
            file_path="data/inbox/example.txt",
            extension=".txt",
            raw_text="原始内容",
            clean_text="清洗内容",
            metadata={"parser": "txt"},
        )
        self.ai_result = AIResult(
            file_name="example.txt",
            file_path="data/inbox/example.txt",
            doc_type="合同",
            summary="摘要",
            keywords=["合同"],
            suggested_folder="合同",
            suggested_name="example_summary",
            confidence=0.9,
        )

    def test_build_done_record(self) -> None:
        result_path = Path(__file__)
        record = build_result_record(
            job=self.job,
            parse_result=self.parse_result,
            ai_result=self.ai_result,
            result_file=result_path,
        )

        self.assertEqual(record.status, "done")
        self.assertEqual(record.doc_type, "合同")
        self.assertEqual(record.result_file, str(result_path))
        self.assertIsNone(record.error_message)

    def test_build_failed_record_from_parse_error(self) -> None:
        record = build_result_record(
            job=self.job,
            error=ParseError("编码解析失败：data/inbox/example.txt"),
        )

        self.assertEqual(record.status, "failed")
        self.assertEqual(record.doc_type, "处理失败")
        self.assertEqual(record.source_file, "example.txt")
        self.assertIn("编码解析失败", record.error_message)

    def test_build_skipped_record_from_unsupported_file_error(self) -> None:
        record = build_result_record(
            job=self.job,
            error=UnsupportedFileError("不支持的文件类型：.pdf"),
        )

        self.assertEqual(record.status, "skipped")
        self.assertEqual(record.doc_type, "已跳过")
        self.assertIn(".pdf", record.error_message)

    def test_invalid_explicit_status_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_result_record(job=self.job, status="processing")


class ResolveRecordStatusTests(unittest.TestCase):
    def test_status_resolution(self) -> None:
        self.assertEqual(resolve_record_status(), "done")
        self.assertEqual(resolve_record_status(error=ParseError("x")), "failed")
        self.assertEqual(
            resolve_record_status(error=UnsupportedFileError("x")),
            "skipped",
        )


if __name__ == "__main__":
    unittest.main()
