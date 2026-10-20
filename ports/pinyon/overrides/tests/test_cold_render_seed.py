"""Old Linux saves can be tested privately without inventing shader catalogs."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('render_seed', Path(__file__).resolve().parents[1] / 'tools/create-render-seed.py')
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


class ColdRenderSeedTests(unittest.TestCase):
    def test_old_save_requires_explicit_cold_cache_and_is_copied_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'old'
            profile = source / 'user/owner/ForzaProfile/ForzaProfile'
            profile.parent.mkdir(parents=True)
            profile.write_bytes(b'existing-player-progress')
            modded = source / 'user-modded/owner/ForzaProfile/ForzaProfile'
            modded.parent.mkdir(parents=True)
            modded.write_bytes(b'newer-modded-progress')
            with self.assertRaisesRegex(ValueError, 'missing FH1 shader catalogs'):
                seed.create_seed(source, root / 'strict')
            self.assertFalse((root / 'strict').exists())
            result = seed.create_seed(source, root / 'snapshot', allow_cold_cache=True)
            self.assertTrue(result['cold_cache'])
            self.assertEqual(result['missing_catalogs'], list(seed.CATALOGS))
            self.assertEqual(result['user_trees'], ['user', 'user-modded'])
            self.assertEqual((root / 'snapshot' / modded.relative_to(source)).read_bytes(), b'newer-modded-progress')
            copied = root / 'snapshot' / profile.relative_to(source)
            self.assertEqual(copied.read_bytes(), profile.read_bytes())
            copied.write_bytes(b'isolated-change')
            self.assertEqual(profile.read_bytes(), b'existing-player-progress')
            self.assertEqual(modded.read_bytes(), b'newer-modded-progress')
            with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
                seed.create_seed(source, root / 'snapshot', allow_cold_cache=True)
