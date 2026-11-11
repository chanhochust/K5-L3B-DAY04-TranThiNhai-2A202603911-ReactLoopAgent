"""Kiểm tra offline bước nhắc đọc incident được liên kết (Bài 4, case H1). Không gọi API."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final

# Snapshot thật: update của h02n9572mx9y liên kết tới xr3myzj7ms51.
READ_H02N = tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"h02n9572mx9y"}')
READ_XR3 = tool_call('2', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}')
ANSWER = final('Đã đối chiếu. Nguồn: https://stspg.io/7pwv28hvkmz8')


def events(result):
    return [t['event'] for t in result['trace']]


class RelatedIncidentTests(unittest.TestCase):
    def test_unread_related_incident_gets_one_reminder(self):
        fake = FakeProvider([READ_H02N, ANSWER, READ_XR3, ANSWER])
        result = run_agent('x', fake, StatusTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        reminder = next(t for t in result['trace'] if t['event'] == 'validation_unread_related')
        self.assertEqual(reminder['unread'], ['xr3myzj7ms51'])
        self.assertIn('xr3myzj7ms51', fake.histories[2][-1]['content'])  # lời nhắc gửi cho model
        tool_steps = {t['step'] for t in result['trace'] if t['event'] == 'tool'}
        self.assertEqual(len(tool_steps), 2)  # đọc incident liên kết ở một step riêng

    def test_reminder_only_once(self):
        fake = FakeProvider([READ_H02N, ANSWER, ANSWER])
        result = run_agent('x', fake, StatusTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(events(result).count('validation_unread_related'), 1)

    def test_no_reminder_without_budget(self):
        fake = FakeProvider([READ_H02N, ANSWER])
        result = run_agent('x', fake, StatusTools(), max_steps=2)
        self.assertEqual(result['status'], 'completed')
        self.assertNotIn('validation_unread_related', events(result))

    def test_no_reminder_when_related_already_read(self):
        both = tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"h02n9572mx9y"}')
        both['calls'] += READ_XR3['calls']
        both['message']['tool_calls'] += READ_XR3['message']['tool_calls']
        result = run_agent('x', FakeProvider([both, ANSWER]), StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertNotIn('validation_unread_related', events(result))

    def test_failed_tool_has_no_related(self):
        missing = tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"missing"}')
        result = run_agent('x', FakeProvider([missing, final('Không tìm thấy')]), StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertNotIn('validation_unread_related', events(result))
        json.dumps(result, ensure_ascii=False)


if __name__ == '__main__':
    unittest.main()
