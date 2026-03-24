import xml.etree.ElementTree as ET

from api.exporters.commerceml import build_commerceml


def test_build_commerceml_valid_xml(sample_receipt_result):
    xml_bytes = build_commerceml([sample_receipt_result])
    root = ET.fromstring(xml_bytes)

    assert root.tag == "КоммерческаяИнформация"


def test_commerceml_contains_document(sample_receipt_result):
    xml_bytes = build_commerceml([sample_receipt_result])
    root = ET.fromstring(xml_bytes)

    documents = root.findall("Документ")
    assert len(documents) >= 1


def test_commerceml_inn_present(sample_receipt_result):
    xml_bytes = build_commerceml([sample_receipt_result])
    root = ET.fromstring(xml_bytes)

    inn_node = root.find("./Документ/Контрагенты/Контрагент/ИНН")
    assert inn_node is not None
    assert inn_node.text == "7701234567"


def test_commerceml_items_count(sample_receipt_result):
    xml_bytes = build_commerceml([sample_receipt_result])
    root = ET.fromstring(xml_bytes)

    product_nodes = root.findall("./Документ/Товары/Товар")
    assert len(product_nodes) == len(sample_receipt_result["items"])


def test_commerceml_none_fields_safe():
    payload = [
        {
            "receipt": {"date": None},
            "merchant": {"organization": None, "inn": None},
            "items": [
                {
                    "name": None,
                    "quantity": None,
                    "price": None,
                    "amount": None,
                    "vat_rate": None,
                    "vat_amount": None,
                }
            ],
            "totals": {"total": None, "total_vat": None},
        }
    ]

    xml_bytes = build_commerceml(payload)
    root = ET.fromstring(xml_bytes)
    assert root.find("./Документ/Товары/Товар") is not None


def test_commerceml_three_documents():
    payload = [
        {
            "id": "r-1",
            "date": "2026-03-20",
            "organization": "ООО Первый",
            "inn": "7701234567",
            "total": 100.0,
            "total_vat": 16.67,
            "items": [{"name": "Товар 1", "quantity": 1, "price": 100.0, "amount": 100.0}],
        },
        {
            "id": "r-2",
            "date": "2026-03-21",
            "organization": "ООО Второй",
            "inn": "7701234567",
            "total": 200.0,
            "total_vat": 33.33,
            "items": [{"name": "Товар 2", "quantity": 1, "price": 200.0, "amount": 200.0}],
        },
        {
            "id": "r-3",
            "date": "2026-03-22",
            "organization": "ООО Третий",
            "inn": "7701234567",
            "total": 300.0,
            "total_vat": 50.0,
            "items": [{"name": "Товар 3", "quantity": 1, "price": 300.0, "amount": 300.0}],
        },
    ]

    xml_bytes = build_commerceml(payload)
    root = ET.fromstring(xml_bytes)
    documents = root.findall("Документ")
    assert len(documents) == 3
