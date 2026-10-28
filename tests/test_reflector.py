"""The reflector: the tolerant parser and the memory line a lesson becomes."""

from dragon.reflector import LESSONS_PER_PASS, lesson_line, parse_lessons


def test_parse_lessons_reads_the_array_and_trims():
    text = (
        '[{"content": "The user prefers morning appointments", '
        '"applies": "booking anything", "about": "appointments, morning"}]'
    )
    lessons = parse_lessons(text)
    assert lessons == [
        {
            "content": "The user prefers morning appointments",
            "applies": "booking anything",
            "about": "appointments, morning",
        }
    ]
    assert (
        lesson_line(lessons[0]) == "The user prefers morning appointments (when: booking anything)"
    )
    assert lesson_line({"content": "Plain", "applies": "", "about": ""}) == "Plain"


def test_parse_lessons_survives_what_models_actually_send():
    assert parse_lessons("no json here") == []
    assert parse_lessons('{"content": "without the rest"}') == [
        {"content": "without the rest", "applies": "", "about": ""}
    ]
    fenced = '```json\n[{"content": "a", "applies": "x", "about": "y"}, {"content": "bad"\n```\n'
    assert [x["content"] for x in parse_lessons(fenced)] == ["a"]
    cut = '[{"content": "one"}, {"content": "two"}, {"content": "thr'
    assert len(parse_lessons(cut)) == 2
    many = "[" + ",".join(f'{{"content": "c{i}"}}' for i in range(10)) + "]"
    assert len(parse_lessons(many)) == LESSONS_PER_PASS
