"""Kiểm tra offline các hành vi bonus của agent: giới hạn retry 429, Retry-After, incident liên kết khác provider."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import agent
from agent import run_agent
from bonus.tools import BonusTools
from bonus.test_agent import ScriptedProvider, call, final


def tool_events(result, name):
    return [t for t in result['trace'] if t['event'] == 'tool' and t['name'] == name]


class BonusRetryTests(unittest.TestCase):
    def test_persistent_429_stops_after_three_calls(self):
        p = ScriptedProvider([call(str(i), 'get_vercel_status', {}) for i in range(4)] + [final('Không xác định được Vercel')])
        result = run_agent('Kiểm tra Vercel', p, BonusTools(scenario='rate_limit_always'), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(tool_events(result, 'get_vercel_status')), 3)  # chỉ 3 lần gọi API thật
        blocked = [t for t in result['trace'] if t['event'] == 'tool_blocked']
        self.assertEqual(len(blocked), 1)
        self.assertEqual(json.loads(p.histories[4][-1]['content'])['error'], 'RETRY_LIMIT_REACHED')

    def test_retry_after_is_respected_with_cap(self):
        class LiveLike(BonusTools):
            def execute(self, name, args):
                return {'ok': False, 'error': 'RATE_LIMITED', 'http_status': 429, 'retry_after': '120'}
        # Lần 1 bị 429, model dừng -> được nhắc thử lại -> lần 2 vẫn 429 -> model báo chưa xác định.
        p = ScriptedProvider([call('a', 'get_npm_status', {}), final('npm chưa xác định'),
                              call('b', 'get_npm_status', {}), final('npm chưa xác định sau 2 lần')])
        with patch.object(agent.time, 'sleep') as sleep:
            result = run_agent('npm', p, LiveLike(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([c.args for c in sleep.call_args_list], [(agent.MAX_TOOL_WAIT,)] * 2)  # 120s -> giới hạn
        self.assertTrue(all(t['waited_seconds'] == agent.MAX_TOOL_WAIT for t in tool_events(result, 'get_npm_status')))

    def test_related_link_uses_provider_from_link_host(self):
        args = {'provider': 'vercel', 'incident_id': 'sps6n39gm4sg', 'offset': 2, 'limit': 3}
        details = BonusTools().execute('get_incident_details', args)
        p = ScriptedProvider([call('a', 'get_incident_details', args), final('Nguồn: ' + details['url']), final('Nguồn: ' + details['url'])])
        result = run_agent('Vercel', p, BonusTools(), max_steps=6)
        reminder = next(t for t in result['trace'] if t['event'] == 'validation_unread_related')
        self.assertEqual(reminder['unread'], ['93njd414rpbx'])
        self.assertIn('93njd414rpbx (provider: github)', p.histories[2][-1]['content'])

    def test_unretried_429_gets_one_reminder(self):
        # B10: model dừng ngay sau 429 đầu tiên -> agent nhắc thử lại; lần sau thành công.
        p = ScriptedProvider([call('a', 'get_vercel_status', {}), final('Vercel lỗi'),
                              call('b', 'get_vercel_status', {}), final('Vercel operational sau khi thử lại')])
        result = run_agent('Kiểm tra Vercel', p, BonusTools(scenario='rate_limit_once'), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        reminder = next(t for t in result['trace'] if t['event'] == 'validation_retry_rate_limited')
        self.assertEqual(reminder['pending'], [{'tool': 'get_vercel_status', 'provider': None, 'attempts': 1}])
        self.assertIn('get_vercel_status', p.histories[2][-1]['content'])
        self.assertEqual(len(tool_events(result, 'get_vercel_status')), 2)

    def test_no_retry_reminder_after_success_or_limit(self):
        ok = ScriptedProvider([call('a', 'get_vercel_status', {}), call('b', 'get_vercel_status', {}), final('ok')])
        done = run_agent('Vercel', ok, BonusTools(scenario='rate_limit_once'), max_steps=6)
        limit = ScriptedProvider([call(str(i), 'get_vercel_status', {}) for i in range(3)] + [final('không xác định')])
        stopped = run_agent('Vercel', limit, BonusTools(scenario='rate_limit_always'), max_steps=6)
        for result in (done, stopped):
            self.assertEqual(result['status'], 'completed')
            self.assertNotIn('validation_retry_rate_limited', [t['event'] for t in result['trace']])

    def test_link_to_unsupported_status_page_is_ignored(self):
        self.assertEqual(agent.find_related_ids(
            {'id': 'x', 'updates': [{'body': 'See https://status.claude.com/incidents/8z7l5zcy0v3b'}]},
            ['github', 'cloudflare', 'vercel', 'npm', 'digitalocean']), [])


if __name__ == '__main__':
    unittest.main()
