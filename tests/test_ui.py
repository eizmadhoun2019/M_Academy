"""T-013 acceptance: the shell, the preview showcase and the error pages."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

ARABIC_SHOWCASE = "/academy/preview/ar/"
ENGLISH_SHOWCASE = "/academy/preview/en/"


def test_the_preview_redirects_to_arabic() -> None:
    response = Client().get("/academy/preview/")

    assert response.status_code == 302
    assert response["Location"] == ARABIC_SHOWCASE


def test_the_arabic_showcase_is_right_to_left() -> None:
    response = Client().get(ARABIC_SHOWCASE)
    html = response.content.decode()

    assert response.status_code == 200
    assert '<html lang="ar" dir="rtl">' in html
    # The catalogue is compiled from the tracked .po, so this asserts the real translation.
    assert "معرض المكوّنات" in html
    assert 'href="/academy/preview/en/"' in html


def test_the_english_showcase_is_left_to_right() -> None:
    response = Client().get(ENGLISH_SHOWCASE)
    html = response.content.decode()

    assert response.status_code == 200
    assert '<html lang="en" dir="ltr">' in html
    assert "Component showcase" in html
    assert 'href="/academy/preview/ar/"' in html


@pytest.mark.parametrize("state", ["loading", "empty", "error", "forbidden", "slow"])
def test_every_sample_state_renders_with_its_own_sample(state: str) -> None:
    response = Client().get(f"{ENGLISH_SHOWCASE}?state={state}")

    assert response.status_code == 200
    assert f'data-state-sample="{state}"' in response.content.decode()


def test_the_empty_state_explains_itself_in_arabic() -> None:
    html = Client().get(f"{ARABIC_SHOWCASE}?state=empty").content.decode()

    assert "لا يوجد تدريب مكلَّف به الآن." in html


@pytest.fixture(autouse=True)
def _preview_profile(settings: Any) -> None:
    """The preview exists only in a development profile, so the suite turns it on."""
    settings.DEBUG = True


@pytest.mark.parametrize("url", [f"{ARABIC_SHOWCASE}?state=unknown", "/academy/preview/fr/"])
def test_an_unknown_state_or_language_is_not_found(url: str) -> None:
    assert Client().get(url).status_code == 404


def test_the_preview_is_absent_outside_a_development_profile(settings: Any) -> None:
    settings.DEBUG = False

    assert Client().get(ARABIC_SHOWCASE).status_code == 404


def test_the_preview_route_has_a_name() -> None:
    assert reverse("academy_ui:preview_showcase", args=["en"]) == ENGLISH_SHOWCASE


def test_an_unknown_path_renders_the_404_page(settings: Any) -> None:
    settings.DEBUG = False
    response = Client().get("/academy/no-such-screen/")
    html = response.content.decode()

    assert response.status_code == 404
    assert "404" in html
    assert "هذه الصفحة غير موجودة" in html


def test_the_forbidden_and_server_pages_render_their_own_text() -> None:
    from academy.ui import errors

    forbidden = errors.forbidden(_request())
    server = errors.server_error(_request())

    assert forbidden.status_code == 403
    assert "لا تملك صلاحية الوصول إلى هذه الصفحة" in forbidden.content.decode()
    assert server.status_code == 500
    assert "حدث خطأ ما" in server.content.decode()


def _request() -> Any:
    from django.test import RequestFactory

    return RequestFactory().get("/")


def test_the_pages_carry_no_inline_style_or_script() -> None:
    for url in (ARABIC_SHOWCASE, ENGLISH_SHOWCASE):
        html = Client().get(url).content.decode()
        assert " style=" not in html
        assert "<script" not in html


class _ControlCollector(HTMLParser):
    """Collect labels and form controls so a control without a label fails the test."""

    def __init__(self) -> None:
        super().__init__()
        self.labels: set[str] = set()
        self.controls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "label" and attributes.get("for"):
            self.labels.add(attributes["for"] or "")
        if tag in {"input", "select", "textarea"} and attributes.get("type") != "hidden":
            self.controls.append(attributes.get("id") or "")


def test_every_form_control_has_a_label() -> None:
    collector = _ControlCollector()
    collector.feed(Client().get(ENGLISH_SHOWCASE).content.decode())

    assert collector.controls
    assert [control for control in collector.controls if control not in collector.labels] == []


def test_the_navigation_links_point_at_real_sections() -> None:
    html = Client().get(ENGLISH_SHOWCASE).content.decode()
    anchors = set(re.findall(r'href="#([a-z]+)"', html))

    assert anchors
    for anchor in anchors:
        assert f'id="{anchor}"' in html


def test_the_stylesheet_and_font_ship_with_the_application() -> None:
    stylesheet = finders.find("css/academy.css")
    font = finders.find("fonts/noto-sans-arabic-arabic.woff2")

    assert stylesheet and font
    with open(stylesheet, encoding="utf-8") as handle:
        css = handle.read()
    assert "--color-brand-gold: #e8aa23" in css
    assert "--color-navy: #101820" in css
    assert "--tap-target: 44px" in css
    # RTL first: no physical left/right declarations outside the mirrored current-row rule.
    assert "margin-left" not in css
    assert "padding-right" not in css
    assert "@media (min-width: 1024px)" in css
    assert "@media (max-width: 767px)" in css


def test_the_showcase_uses_the_default_language_of_the_project() -> None:
    assert settings.LANGUAGE_CODE == "ar"
