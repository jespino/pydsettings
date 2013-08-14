import unittest
import warnings

from pysettings import signals
from pysettings.conf import settings
from pysettings.decorators import override_settings
import six


@override_settings(TEST='override', TEST_OUTER='outer')
class FullyDecoratedTranTestCase(unittest.TestCase):

    available_apps = []

    def test_override(self):
        self.assertEqual(settings.TEST, 'override')
        self.assertEqual(settings.TEST_OUTER, 'outer')

    @override_settings(TEST='override2')
    def test_method_override(self):
        self.assertEqual(settings.TEST, 'override2')
        self.assertEqual(settings.TEST_OUTER, 'outer')

    def test_decorated_testcase_name(self):
        self.assertEqual(FullyDecoratedTranTestCase.__name__, 'FullyDecoratedTranTestCase')

    def test_decorated_testcase_module(self):
        self.assertEqual(FullyDecoratedTranTestCase.__module__, __name__)


@override_settings(TEST='override')
class FullyDecoratedTestCase(unittest.TestCase):

    def test_override(self):
        self.assertEqual(settings.TEST, 'override')

    @override_settings(TEST='override2')
    def test_method_override(self):
        self.assertEqual(settings.TEST, 'override2')


class ClassDecoratedTestCaseSuper(unittest.TestCase):
    """
    Dummy class for testing max recursion error in child class call to
    super().  Refs #17011.

    """
    def test_max_recursion_error(self):
        pass


@override_settings(TEST='override')
class ClassDecoratedTestCase(ClassDecoratedTestCaseSuper):
    def test_override(self):
        self.assertEqual(settings.TEST, 'override')

    @override_settings(TEST='override2')
    def test_method_override(self):
        self.assertEqual(settings.TEST, 'override2')

    def test_max_recursion_error(self):
        """
        Overriding a method on a super class and then calling that method on
        the super class should not trigger infinite recursion. See #17011.

        """
        try:
            super(ClassDecoratedTestCase, self).test_max_recursion_error()
        except RuntimeError:
            self.fail()


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.testvalue = None
        signals.setting_changed.connect(self.signal_callback)

    def tearDown(self):
        signals.setting_changed.disconnect(self.signal_callback)

    def signal_callback(self, sender, setting, value, **kwargs):
        if setting == 'TEST':
            self.testvalue = value

    def test_override(self):
        settings.TEST = 'test'
        self.assertEqual('test', settings.TEST)
        with self.settings(TEST='override'):
            self.assertEqual('override', settings.TEST)
        self.assertEqual('test', settings.TEST)
        del settings.TEST

    def test_override_change(self):
        settings.TEST = 'test'
        self.assertEqual('test', settings.TEST)
        with self.settings(TEST='override'):
            self.assertEqual('override', settings.TEST)
            settings.TEST = 'test2'
        self.assertEqual('test', settings.TEST)
        del settings.TEST

    def test_override_doesnt_leak(self):
        self.assertRaises(AttributeError, getattr, settings, 'TEST')
        with self.settings(TEST='override'):
            self.assertEqual('override', settings.TEST)
            settings.TEST = 'test'
        self.assertRaises(AttributeError, getattr, settings, 'TEST')

    @override_settings(TEST='override')
    def test_decorator(self):
        self.assertEqual('override', settings.TEST)

    def test_context_manager(self):
        self.assertRaises(AttributeError, getattr, settings, 'TEST')
        override = override_settings(TEST='override')
        self.assertRaises(AttributeError, getattr, settings, 'TEST')
        override.enable()
        self.assertEqual('override', settings.TEST)
        override.disable()
        self.assertRaises(AttributeError, getattr, settings, 'TEST')

    def test_signal_callback_context_manager(self):
        self.assertRaises(AttributeError, getattr, settings, 'TEST')
        with self.settings(TEST='override'):
            self.assertEqual(self.testvalue, 'override')
        self.assertEqual(self.testvalue, None)

    @override_settings(TEST='override')
    def test_signal_callback_decorator(self):
        self.assertEqual(self.testvalue, 'override')

    #
    # Regression tests for #10130: deleting settings.
    #

    def test_settings_delete(self):
        settings.TEST = 'test'
        self.assertEqual('test', settings.TEST)
        del settings.TEST
        self.assertRaises(AttributeError, getattr, settings, 'TEST')

    def test_settings_delete_wrapped(self):
        self.assertRaises(TypeError, delattr, settings, '_wrapped')

    def test_override_settings_delete(self):
        """
        Allow deletion of a setting in an overridden settings set (#18824)
        """
        previous_i18n = settings.USE_I18N
        with self.settings(USE_I18N=False):
            del settings.USE_I18N
            self.assertRaises(AttributeError, getattr, settings, 'USE_I18N')
        self.assertEqual(settings.USE_I18N, previous_i18n)

    def test_override_settings_nested(self):
        """
        Test that override_settings uses the actual _wrapped attribute at
        runtime, not when it was instantiated.
        """

        self.assertRaises(AttributeError, getattr, settings, 'TEST')
        self.assertRaises(AttributeError, getattr, settings, 'TEST2')

        inner = override_settings(TEST2='override')
        with override_settings(TEST='override'):
            self.assertEqual('override', settings.TEST)
            with inner:
                self.assertEqual('override', settings.TEST)
                self.assertEqual('override', settings.TEST2)
            # inner's __exit__ should have restored the settings of the outer
            # context manager, not those when the class was instantiated
            self.assertEqual('override', settings.TEST)
            self.assertRaises(AttributeError, getattr, settings, 'TEST2')

        self.assertRaises(AttributeError, getattr, settings, 'TEST')
        self.assertRaises(AttributeError, getattr, settings, 'TEST2')
