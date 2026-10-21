"""Optional upstream launcher selection. GPL-3.0-only, MASELKO-95, 2026-10-21."""
from pathlib import Path
import os

from .network import UserError


class LaunchOptions:
    def __init__(self, launcher):
        self.launcher = launcher

    def root(self, install):
        if install.get('source_id') != 'pinyon' or self.launcher.system_key() != 'linux':
            return None
        try:
            root = self.launcher.port_setup.root(install)
        except (KeyError, UserError):
            return None
        return root if (root / 'tools/pinyon.py').is_file() else None

    def executable(self, install):
        root = self.root(install)
        if root is None:
            return None
        name = 'PinyonShiftLauncher.exe' if self.launcher.system_key() == 'windows' else 'PinyonShiftLauncher'
        candidates = [root / '.local/recopile-launcher' / name]
        if install.get('runtime_dir'):
            runtime = Path(install['runtime_dir'])
            candidates += [runtime / 'PinyonShift' / name, runtime / name]
        return next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)

    def information(self, ident, install):
        if self.root(install) is None:
            return None
        preference = self.launcher.store.get('settings', 'launch-choice:' + ident, {})
        preferred = preference.get('mode', 'ask')
        return {'preferred': preferred if preferred in {'ask', 'game', 'launcher'} else 'ask',
                'launcher_available': self.executable(install) is not None,
                'launcher_name': 'Pinyon Shift',
                'repository': 'https://github.com/arcanite24/pinyon-shift'}

    def select(self, ident, game, install, mode, remember):
        if mode is not None and (not isinstance(mode, str) or mode not in {'ask', 'game', 'launcher'}):
            raise UserError('Nieznany sposób uruchamiania gry.')
        if remember is not None and type(remember) is not bool:
            raise UserError('Niepoprawna opcja zapamiętania wyboru.')
        information = self.information(ident, install)
        if information is None:
            if mode in {'ask', 'launcher'}:
                raise UserError('Ten projekt nie ma podłączonego oryginalnego launchera.')
            return 'game', None
        if mode is None:
            mode = information['preferred']
        # A remembered GUI choice must remain recoverable after moving or
        # upgrading an installation, rather than preventing direct Play.
        if mode == 'ask' or (mode == 'launcher' and not information['launcher_available'] and remember is None):
            return None, {'launch_choice_required': True, 'game_id': ident,
                          'title': game['title'], **information}
        return mode, None

    def command(self, install, environment):
        root = self.root(install)
        executable = self.executable(install)
        if root is None or executable is None:
            raise UserError('Zaktualizuj narzędzia Pinyon Shift do pakietu z oryginalnym launcherem.')
        user = Path(install['user_root'])
        state = Path(install.get('pinyon_state_root') or user / 'pinyon')
        game = root / '.local/game/base'
        if not (game / 'default.xex').is_file():
            candidate = Path(install.get('data_path') or game)
            if not (candidate / 'default.xex').is_file():
                raise UserError('Najpierw przygotuj własne pliki gry w RE:COPILE.')
            game = candidate
        environment = {**environment,
                       'PINYON_SHIFT_SOURCE_ROOT': str(root.resolve()),
                       'PINYON_SHIFT_STATE_ROOT': str(state.resolve()),
                       'PINYON_SHIFT_GAME_ROOT': str(game.resolve()),
                       'PINYON_SHIFT_INSTALL_ROOT': str((user / 'pinyon-launcher').resolve()),
                       'PINYON_SHIFT_UPDATE_CHECK': '0',
                       'DOTNET_BUNDLE_EXTRACT_BASE_DIR': str((user / 'cache/pinyon-launcher').resolve())}
        return [str(executable)], root, environment

    def remember(self, ident, mode, remember):
        if remember is not None:
            self.launcher.store.put('settings', 'launch-choice:' + ident,
                                    {'mode': mode if remember else 'ask'})
