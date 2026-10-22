import contextlib
import io
import unittest
from cse3461_chat.config import parse_server_args, parse_client_args


class ConfigTests(unittest.TestCase):
    def test_config_defaults_and_rejections(self):
        server = parse_server_args([])
        self.assertEqual((server.host, server.port, server.max_clients, server.features),
                         ('127.0.0.1', 3461, 16, 'none'))
        for features in ('f1', 'f2', 'f1,f2'):
            self.assertEqual(parse_server_args(['--features', features]).features, features)
        self.assertEqual(parse_client_args(['--username', 'Alice']).username, 'Alice')
        for parser, args in [(parse_server_args, ['--port', '0']),
                             (parse_client_args, ['--port', '65536']),
                             (parse_server_args, ['--max-clients', '0']),
                             (parse_server_args, ['--features', 'f3']),
                             (parse_server_args, ['--features', 'f2,f1']),
                             (parse_server_args, ['--host', '999.999.999.999']),
                             (parse_client_args, ['--username', 'bad name']),
                             (parse_client_args, ['--host', '0.0.0.0'])]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as err:
                    parser(args)
                self.assertEqual(err.exception.code, 2)
