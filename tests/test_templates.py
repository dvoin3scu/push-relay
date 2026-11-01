import unittest

from push_relay.templates import render, render_string


class RenderTest(unittest.TestCase):
    def test_variables_and_sections(self):
        view = {"a": "A", "b": "", "n": 3}
        self.assertEqual(render_string("{{a}}{{#b}} · {{b}}{{/b}}", view), "A")
        self.assertEqual(render_string("{{a}}{{#a}} · {{n}}{{/a}}", view), "A · 3")
        self.assertEqual(render_string("{{b}}{{^b}}fallback{{/b}}", view), "fallback")
        self.assertEqual(render_string("{{#a}}{{#b}}x{{/b}}y{{/a}}", view), "y")

    def test_raw_values_and_empty_fields_dropped(self):
        out = render({"tags": "{{tags}}", "priority": "{{p}}", "click": "{{url}}", "t": " {{e}} x"},
                     {"tags": ["tv"], "p": 4, "url": "", "e": ""})
        self.assertEqual(out, {"tags": ["tv"], "priority": 4, "t": "x"})


if __name__ == "__main__":
    unittest.main()
