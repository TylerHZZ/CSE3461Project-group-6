import unittest
from cse3461_chat.commands import parse_input, LocalUsageError, safe_display


class CommandTests(unittest.TestCase):
    def test_command_grammar(self):
        for line,kind,data in [(' hello ','broadcast_send',{'text':' hello '}),
                                ('/all @literal','broadcast_send',{'text':'@literal'}),
                                ('@bob  hi','private_send',{'to':'bob','text':' hi'}),
                                ('@bob\thi','private_send',{'to':'bob','text':'hi'}),
                                ('/enhance','enhancement_request',{})]:
            command=parse_input(line)
            self.assertEqual((command.kind,command.type,command.data),('send',kind,data))
        for line in ['@','@bob','@bad-name hi','@bob   ','/wat','/all','', '  ']:
            self.assertIsInstance(parse_input(line),LocalUsageError)
        self.assertEqual(parse_input('/help').kind,'help')
        self.assertEqual(parse_input('/quit').kind,'quit')

    def test_untrusted_display_is_escaped(self):
        result=safe_display('bad\x1b[2J\u202e\nname')
        self.assertNotIn('\x1b',result)
        self.assertNotIn('\u202e',result)
        self.assertNotIn('\n',result)
        self.assertIn('name',result)
