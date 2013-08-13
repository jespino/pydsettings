import os
import unittest
import warnings

from pysettings import settings, global_settings
from pysettings.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.test import SimpleTestCase, TransactionTestCase, TestCase, signals
from django.test.utils import override_settings
import six


@override_settings(TEST='override', TEST_OUTER='outer')
class FullyDecoratedTranTestCase(TransactionTestCase):

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
class FullyDecoratedTestCase(TestCase):

    def test_override(self):
        self.assertEqual(settings.TEST, 'override')

    @override_settings(TEST='override2')
    def test_method_override(self):
        self.assertEqual(settings.TEST, 'override2')


class ClassDecoratedTestCaseSuper(TestCase):
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


class SettingsTests(TestCase):
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

    def test_class_decorator(self):
        # SimpleTestCase can be decorated by override_settings, but not ut.TestCase
        class SimpleTestCaseSubclass(SimpleTestCase):
            pass

        class UnittestTestCaseSubclass(unittest.TestCase):
            pass

        decorated = override_settings(TEST='override')(SimpleTestCaseSubclass)
        self.assertIsInstance(decorated, type)
        self.assertTrue(issubclass(decorated, SimpleTestCase))

        with six.assertRaisesRegex(self, Exception,
                "Only subclasses of Django SimpleTestCase*"):
            decorated = override_settings(TEST='override')(UnittestTestCaseSubclass)

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


class TestComplexSettingOverride(TestCase):
    def setUp(self):
        self.old_warn_override_settings = signals.COMPLEX_OVERRIDE_SETTINGS.copy()
        signals.COMPLEX_OVERRIDE_SETTINGS.add('TEST_WARN')

    def tearDown(self):
        signals.COMPLEX_OVERRIDE_SETTINGS = self.old_warn_override_settings
        self.assertFalse('TEST_WARN' in signals.COMPLEX_OVERRIDE_SETTINGS)

    def test_complex_override_warning(self):
        """Regression test for #19031"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            override = override_settings(TEST_WARN='override')
            override.enable()
            self.assertEqual('override', settings.TEST_WARN)
            override.disable()

            self.assertEqual(len(w), 1)
            self.assertEqual('Overriding setting TEST_WARN can lead to unexpected behaviour.', str(w[-1].message))
