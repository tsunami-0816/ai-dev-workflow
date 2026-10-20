"""中文友好的文本切分。"""
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 中文分隔符优先：段落、换行、句号、问号、感叹号、分号、逗号、空格
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


def get_splitter(chunk_size: int = 500, chunk_overlap: int = 50) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_SEPARATORS,
        length_function=len,
    )


def split_documents(docs: List[Document], chunk_size: int = 500, chunk_overlap: int = 50) -> List[Document]:
    return get_splitter(chunk_size, chunk_overlap).split_documents(docs)
