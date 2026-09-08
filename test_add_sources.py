from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from add_sources import set_hyperlink_target


def test_set_hyperlink_target_replaces_cloned_relationship() -> None:
    document = Document()
    paragraph = document.add_paragraph()
    old_id = paragraph.part.relate_to(
        "https://example.com/old", RT.HYPERLINK, is_external=True
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), old_id)
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "https://example.com/new"
    run.append(text)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)

    set_hyperlink_target(paragraph, "https://example.com/new")

    new_id = hyperlink.get(qn("r:id"))
    assert paragraph.part.rels[new_id].target_ref == "https://example.com/new"
