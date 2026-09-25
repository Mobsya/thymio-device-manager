"""Check dependency command environments without requiring native compilers."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'build_dependency', Path(__file__).resolve().parents[1] / 'scripts/build_dependency.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


class OpenSSLEnvironmentTests(unittest.TestCase):
    make_environment = {
        'MAKE': 'make',
        'MAKEFLAGS': ' -- JOBS=2 PRESET=windows-x64 PYTHON=python',
        'MFLAGS': '-j2',
        'MAKELEVEL': '1',
        'MAKEOVERRIDES': '${-*-command-variables-*-}',
        'GNUMAKEFLAGS': '--output-sync',
    }

    def commands(self, platform):
        environment = dict(self.make_environment)
        environment.update(PATH='fixture-tools', PERL=r'C:\Strawberry\perl\bin\perl.exe',
                           INCLUDE='msvc-include', LIB='msvc-lib')
        argv = ['build_dependency.py', 'openssl', '--source', '.', '--prefix', '.',
                '--arch', 'x86_64', '--deployment-target', '11.0', '--jobs', '2']
        calls = []
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(sys, 'platform', platform), patch.object(sys, 'argv', argv), \
             patch.object(recipe, 'run', side_effect=lambda command, source, env:
                          calls.append((list(command), source, dict(env)))):
            recipe.main()
            self.assertEqual(dict(os.environ), environment)
        return calls, environment

    def test_windows_excludes_outer_make_settings(self):
        calls, original = self.commands('win32')
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0][0], original['PERL'])
        self.assertEqual(calls[1][0], ['nmake'])
        self.assertEqual(calls[2][0], ['nmake', 'install_sw'])
        expected = {key: value for key, value in original.items() if key not in self.make_environment}
        for command, source, environment in calls:
            with self.subTest(command=command):
                self.assertEqual(environment, expected)

    def test_windows_uses_openssl_static_library_configuration(self):
        calls, _ = self.commands('win32')
        configure = calls[0][0]
        self.assertEqual(configure[2], 'VC-WIN64A')
        self.assertIn('no-shared', configure)
        self.assertNotIn('-static', configure)

    def test_unix_keeps_make_settings(self):
        for platform in ['linux', 'darwin']:
            with self.subTest(platform=platform):
                calls, original = self.commands(platform)
                self.assertEqual(calls[1][0], ['make', '-j2'])
                self.assertEqual(calls[2][0], ['make', '-j2', 'install_sw'])
                expected = dict(original)
                if platform == 'darwin':
                    expected['MACOSX_DEPLOYMENT_TARGET'] = '11.0'
                for command, source, environment in calls:
                    self.assertEqual(environment, expected)


if __name__ == '__main__':
    unittest.main()
