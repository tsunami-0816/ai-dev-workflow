#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2：套餐列表/详情（分页、边界、404、无鉴权可读）。"""
import pytest

from api.package_api import package_detail, packages
from common.assert_util import assert_err, assert_ok

pytestmark = pytest.mark.l2


def test_list_default_four_packages(api):
    data = assert_ok(packages(api))
    assert data["total"] == 4
    assert data["page"] == 1 and data["size"] == 10
    assert len(data["list"]) == 4
    first = data["list"][0]
    assert first["id"] == 1
    assert first["title"] == "城市轻写真"
    assert float(first["price"]) == 399.0
    assert first["tags"] == ["室内", "2套服装", "精修8张"]
    assert first["status"] == 1


def test_list_size_two_pagination(api):
    page1 = assert_ok(packages(api, 1, 2))
    page2 = assert_ok(packages(api, 2, 2))
    assert page1["total"] == 4 and page2["total"] == 4
    assert len(page1["list"]) == 2 and len(page2["list"]) == 2
    assert {x["id"] for x in page1["list"]} != {x["id"] for x in page2["list"]}


def test_list_page_zero_normalized(api):
    data = assert_ok(packages(api, 0, 10))
    assert data["page"] == 1


def test_list_page_negative_normalized(api):
    data = assert_ok(packages(api, -3, 10))
    assert data["page"] == 1


def test_list_size_over_50_normalized_to_10(api):
    data = assert_ok(packages(api, 1, 999))
    assert data["size"] == 10


def test_list_size_zero_normalized_to_10(api):
    data = assert_ok(packages(api, 1, 0))
    assert data["size"] == 10


def test_list_page_beyond_range_returns_empty(api):
    data = assert_ok(packages(api, 9, 10))
    assert data["list"] == []
    assert data["total"] == 4


def test_detail_second_package(api):
    data = assert_ok(package_detail(api, 2))
    assert data["id"] == 2
    assert data["title"] == "复古胶片"
    assert float(data["price"]) == 499.0
    assert "外景" in data["tags"]
    assert len(data["summary"]) > 0


def test_detail_not_found(api):
    assert_err(package_detail(api, 999), 404, 40401)


def test_detail_zero_not_found(api):
    assert_err(package_detail(api, 0), 404, 40401)


def test_packages_anonymous_readable(cfg):
    from common.request_util import ApiClient
    anon = ApiClient(cfg["base_url"], name="anon")
    assert_ok(packages(anon, 1, 1))
