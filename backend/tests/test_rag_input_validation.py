
import pytest
from pydantic import ValidationError

from app.schemas.rag import RAGQueryRequest


@pytest.mark.parametrize(
    "query",
    [
        "",
        " ",
        "\t",
        "\n",
        " \t\n ",
    ],
)
def test_blank_queries_are_rejected(query):
    with pytest.raises(ValidationError):
        RAGQueryRequest(query=query)


def test_query_is_trimmed():
    request = RAGQueryRequest(
        query="  Find my project notes  ",
    )

    assert request.query == "Find my project notes"


def test_maximum_query_length_is_accepted():
    request = RAGQueryRequest(query="x" * 5000)

    assert len(request.query) == 5000


def test_query_over_maximum_length_is_rejected():
    with pytest.raises(ValidationError):
        RAGQueryRequest(query="x" * 5001)


def test_document_ids_default_to_empty_list():
    request = RAGQueryRequest(query="Search my notes")

    assert request.document_ids == []


def test_more_than_twenty_document_ids_are_rejected():
    with pytest.raises(ValidationError):
        RAGQueryRequest(
            query="Search my notes",
            document_ids=[f"doc-{index}" for index in range(21)],
        )
