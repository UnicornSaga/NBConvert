from collections import OrderedDict
from unittest.mock import Mock

import pytest
from nbformat.v4 import new_code_cell

from nbconvert import translators
from nbconvert.exceptions import NBConvertlException
from nbconvert.models import Parameter


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("foo", '"foo"'),
        ('{"foo": "bar"}', '"{\\"foo\\": \\"bar\\"}"'),
        ({"foo": "bar"}, '{"foo": "bar"}'),
        ({"foo": '"bar"'}, '{"foo": "\\"bar\\""}'),
        ({"foo": ["bar"]}, '{"foo": ["bar"]}'),
        ({"foo": {"bar": "baz"}}, '{"foo": {"bar": "baz"}}'),
        ({"foo": {"bar": '"baz"'}}, '{"foo": {"bar": "\\"baz\\""}}'),
        (["foo"], '["foo"]'),
        (["foo", '"bar"'], '["foo", "\\"bar\\""]'),
        ([{"foo": "bar"}], '[{"foo": "bar"}]'),
        ([{"foo": '"bar"'}], '[{"foo": "\\"bar\\""}]'),
        (12345, '12345'),
        (-54321, '-54321'),
        (1.2345, '1.2345'),
        (-5432.1, '-5432.1'),
        (float('nan'), "float('nan')"),
        (float('-inf'), "float('-inf')"),
        (float('inf'), "float('inf')"),
        (True, 'True'),
        (False, 'False'),
        (None, 'None'),
    ],
)
def test_translate_type_python(test_input, expected):
    assert translators.PythonTranslator.translate(test_input) == expected


@pytest.mark.parametrize(
    "parameters,expected",
    [
        ({"foo": "bar"}, '# Parameters\nfoo = "bar"\n'),
        ({"foo": True}, '# Parameters\nfoo = True\n'),
        ({"foo": 5}, '# Parameters\nfoo = 5\n'),
        ({"foo": 1.1}, '# Parameters\nfoo = 1.1\n'),
        ({"foo": ['bar', 'baz']}, '# Parameters\nfoo = ["bar", "baz"]\n'),
        ({"foo": {'bar': 'baz'}}, '# Parameters\nfoo = {"bar": "baz"}\n'),
        (
            OrderedDict([['foo', 'bar'], ['baz', ['buz']]]),
            '# Parameters\nfoo = "bar"\nbaz = ["buz"]\n',
        ),
    ],
)
def test_translate_codify_python(parameters, expected):
    assert translators.PythonTranslator.codify(parameters) == expected


@pytest.mark.parametrize("test_input,expected", [("", '#'), ("foo", '# foo'), ("['best effort']", "# ['best effort']")])
def test_translate_comment_python(test_input, expected):
    assert translators.PythonTranslator.comment(test_input) == expected


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("a = 2", [Parameter("a", "None", "2", "")]),
        ("a: int = 2", [Parameter("a", "int", "2", "")]),
        ("a = 2 # type:int", [Parameter("a", "int", "2", "")]),
        ("a = False # Nice variable a", [Parameter("a", "None", "False", "Nice variable a")]),
        (
            "a: float = 2.258 # type: int Nice variable a",
            [Parameter("a", "float", "2.258", "Nice variable a")],
        ),
        (
            "a = 'this is a string' # type: int Nice variable a",
            [Parameter("a", "int", "'this is a string'", "Nice variable a")],
        ),
        (
            "a: List[str] = ['this', 'is', 'a', 'string', 'list'] # Nice variable a",
            [Parameter("a", "List[str]", "['this', 'is', 'a', 'string', 'list']", "Nice variable a")],
        ),
        (
            "a: List[str] = [\n    'this', # First\n    'is',\n    'a',\n    'string',\n    'list' # Last\n] # Nice variable a",  # noqa
            [Parameter("a", "List[str]", "['this','is','a','string','list']", "Nice variable a")],
        ),
        (
            "a: List[str] = [\n    'this',\n    'is',\n    'a',\n    'string',\n    'list'\n] # Nice variable a",
            [Parameter("a", "List[str]", "['this','is','a','string','list']", "Nice variable a")],
        ),
        (
            """a: List[str] = [
                'this', # First
                'is',

                'a',
                'string',
                'list' # Last
            ] # Nice variable a

            b: float = -2.3432 # My b variable
            """,
            [
                Parameter("a", "List[str]", "['this','is','a','string','list']", "Nice variable a"),
                Parameter("b", "float", "-2.3432", "My b variable"),
            ],
        ),
    ],
)
def test_inspect_python(test_input, expected):
    cell = new_code_cell(source=test_input)
    assert translators.PythonTranslator.inspect(cell) == expected


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("foo", '"foo"'),
        ('{"foo": "bar"}', '"{\\"foo\\": \\"bar\\"}"'),
        ({"foo": "bar"}, 'list("foo" = "bar")'),
        ({"foo": '"bar"'}, 'list("foo" = "\\"bar\\"")'),
        ({"foo": ["bar"]}, 'list("foo" = list("bar"))'),
        ({"foo": {"bar": "baz"}}, 'list("foo" = list("bar" = "baz"))'),
        ({"foo": {"bar": '"baz"'}}, 'list("foo" = list("bar" = "\\"baz\\""))'),
        (["foo"], 'list("foo")'),
        (["foo", '"bar"'], 'list("foo", "\\"bar\\"")'),
        ([{"foo": "bar"}], 'list(list("foo" = "bar"))'),
        ([{"foo": '"bar"'}], 'list(list("foo" = "\\"bar\\""))'),
        (12345, '12345'),
        (-54321, '-54321'),
        (1.2345, '1.2345'),
        (-5432.1, '-5432.1'),
        (True, 'TRUE'),
        (False, 'FALSE'),
        (None, 'NULL'),
    ],
)
def test_translate_type_r(test_input, expected):
    assert translators.RTranslator.translate(test_input) == expected


@pytest.mark.parametrize("test_input,expected", [("", '#'), ("foo", '# foo'), ("['best effort']", "# ['best effort']")])
def test_translate_comment_r(test_input, expected):
    assert translators.RTranslator.comment(test_input) == expected


@pytest.mark.parametrize(
    "parameters,expected",
    [
        ({"foo": "bar"}, '# Parameters\nfoo = "bar"\n'),
        ({"foo": True}, '# Parameters\nfoo = TRUE\n'),
        ({"foo": 5}, '# Parameters\nfoo = 5\n'),
        ({"foo": 1.1}, '# Parameters\nfoo = 1.1\n'),
        ({"foo": ['bar', 'baz']}, '# Parameters\nfoo = list("bar", "baz")\n'),
        ({"foo": {'bar': 'baz'}}, '# Parameters\nfoo = list("bar" = "baz")\n'),
        (
            OrderedDict([['foo', 'bar'], ['baz', ['buz']]]),
            '# Parameters\nfoo = "bar"\nbaz = list("buz")\n',
        ),
        # Underscores remove
        ({"___foo": 5}, '# Parameters\nfoo = 5\n'),
    ],
)
def test_translate_codify_r(parameters, expected):
    assert translators.RTranslator.codify(parameters) == expected


def test_find_translator_with_exact_kernel_name():
    my_new_kernel_translator = Mock()
    my_new_language_translator = Mock()
    translators.nbconvert_translators.register("my_new_kernel", my_new_kernel_translator)
    translators.nbconvert_translators.register("my_new_language", my_new_language_translator)
    assert (
        translators.nbconvert_translators.find_translator("my_new_kernel", "my_new_language")
        is my_new_kernel_translator
    )


def test_find_translator_with_exact_language():
    my_new_language_translator = Mock()
    translators.nbconvert_translators.register("my_new_language", my_new_language_translator)
    assert (
        translators.nbconvert_translators.find_translator("unregistered_kernel", "my_new_language")
        is my_new_language_translator
    )


def test_find_translator_with_no_such_kernel_or_language():
    with pytest.raises(NBConvertlException):
        translators.nbconvert_translators.find_translator("unregistered_kernel", "unregistered_language")


def test_translate_uses_str_representation_of_unknown_types():
    class FooClass:
        def __str__(self):
            return "foo"

    obj = FooClass()
    assert translators.Translator.translate(obj) == '"foo"'


def test_translator_must_implement_translate_dict():
    class MyNewTranslator(translators.Translator):
        pass

    with pytest.raises(NotImplementedError):
        MyNewTranslator.translate_dict({"foo": "bar"})


def test_translator_must_implement_translate_list():
    class MyNewTranslator(translators.Translator):
        pass

    with pytest.raises(NotImplementedError):
        MyNewTranslator.translate_list(["foo", "bar"])


def test_translator_must_implement_comment():
    class MyNewTranslator(translators.Translator):
        pass

    with pytest.raises(NotImplementedError):
        MyNewTranslator.comment("foo")


# Bash/sh section
@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("foo", "foo"),
        ("foo space", "'foo space'"),
        ("foo's apostrophe", "'foo'\"'\"'s apostrophe'"),
        ("shell ( is ) <dumb>", "'shell ( is ) <dumb>'"),
        (12345, '12345'),
        (-54321, '-54321'),
        (1.2345, '1.2345'),
        (-5432.1, '-5432.1'),
        (True, 'true'),
        (False, 'false'),
        (None, ''),
    ],
)
def test_translate_type_sh(test_input, expected):
    assert translators.BashTranslator.translate(test_input) == expected


@pytest.mark.parametrize("test_input,expected", [("", '#'), ("foo", '# foo'), ("['best effort']", "# ['best effort']")])
def test_translate_comment_sh(test_input, expected):
    assert translators.BashTranslator.comment(test_input) == expected


@pytest.mark.parametrize(
    "parameters,expected",
    [
        ({"foo": "bar"}, '# Parameters\nfoo=bar\n'),
        ({"foo": "shell ( is ) <dumb>"}, "# Parameters\nfoo='shell ( is ) <dumb>'\n"),
        ({"foo": True}, '# Parameters\nfoo=true\n'),
        ({"foo": 5}, '# Parameters\nfoo=5\n'),
        ({"foo": 1.1}, '# Parameters\nfoo=1.1\n'),
        (
            OrderedDict([['foo', 'bar'], ['baz', '$dumb(shell)']]),
            "# Parameters\nfoo=bar\nbaz='$dumb(shell)'\n",
        ),
    ],
)
def test_translate_codify_sh(parameters, expected):
    assert translators.BashTranslator.codify(parameters) == expected
