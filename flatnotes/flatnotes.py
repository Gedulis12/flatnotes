import glob
import os
import re
from datetime import datetime
from typing import List, Literal, Set, Tuple

import whoosh
from whoosh import writing
from whoosh.analysis import CharsetFilter, StemmingAnalyzer
from whoosh.fields import DATETIME, ID, KEYWORD, TEXT, SchemaClass
from whoosh.highlight import ContextFragmenter, WholeFragmenter
from whoosh.index import Index
from whoosh.qparser import MultifieldParser
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.query import Every
from whoosh.searching import Hit
from whoosh.support.charset import accent_map

from helpers import empty_dir, re_extract, strip_ext
from logger import logger

MARKDOWN_EXT = ".md"
INDEX_SCHEMA_VERSION = "3"

StemmingFoldingAnalyzer = StemmingAnalyzer() | CharsetFilter(accent_map)


class IndexSchema(SchemaClass):
    filename = ID(unique=True, stored=True)
    last_modified = DATETIME(stored=True, sortable=True)
    title = TEXT(
        field_boost=2.0, analyzer=StemmingFoldingAnalyzer, sortable=True
    )
    content = TEXT(analyzer=StemmingFoldingAnalyzer)
    tags = KEYWORD(lowercase=True, field_boost=2.0)


class InvalidTitleError(Exception):
    def __init__(self, message="The specified title is invalid"):
        self.message = message
        super().__init__(self.message)


class Note:
    def __init__(
            self, flatnotes: "Flatnotes", title: str, new: bool = False) -> None:
        self._flatnotes = flatnotes
        self._title = title.strip()
        self.subdirs = os.path.join("")
        if not self._is_valid_title(self._title):
            raise InvalidTitleError
        if new and os.path.exists(self.filepath):
            raise FileExistsError
        elif new:
            open(self.filepath, "w").close()

    def set_subdirs(self, subdirs):
        self.subdirs = subdirs

    @property
    def filepath(self):
#        return os.path.join(self._flatnotes.dir, self.subdirs, self.filename)
#        filepath = os.path.join(self._flatnotes.dir, self.subdirs, self.filename)
        filepath = os.path.join("")
        dirlist = glob.glob(os.path.join(self._flatnotes.dir, "**/*" + MARKDOWN_EXT), recursive=True)
        for file in dirlist:
            if self.filename in file:
                filepath = file
        return filepath

    @property
    def dir_listing(self):
        return os.walk(self._flatnotes.dir)

    @property
    def filename(self):
        return self._title + MARKDOWN_EXT

    @property
    def last_modified(self):
        return os.path.getmtime(self.filepath)

    # Editable Properties
    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, new_title):
        new_title = new_title.strip()
        if not self._is_valid_title(new_title):
            raise InvalidTitleError
        new_filepath = os.path.join(
            self._flatnotes.dir, self.subdirs, new_title + MARKDOWN_EXT
        )
        os.rename(self.filepath, new_filepath)
        self._title = new_title

    @property
    def content(self):
        with open(self.filepath, "r", encoding="utf-8") as f:
            return f.read()

    @content.setter
    def content(self, new_content):
        if not os.path.exists(self.filepath):
            raise FileNotFoundError
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    def delete(self):
        os.remove(self.filepath)

    # Functions
    def _is_valid_title(self, title: str) -> bool:
        r"""Return False if the declared title contains any of the following
        characters: <>:"/\|?*"""
        invalid_chars = r'<>:"/\|?*'
        return not any(invalid_char in title for invalid_char in invalid_chars)


class SearchResult(Note):
    def __init__(self, flatnotes: "Flatnotes", hit: Hit) -> None:
        super().__init__(flatnotes, strip_ext(hit["filename"]))

        self._matched_fields = self._get_matched_fields(hit.matched_terms())
        # If the search was ordered using a text field then hit.score is the
        # value of that field. This isn't useful so only set self._score if it
        # is a float.
        self._score = hit.score if type(hit.score) is float else None

        if "title" in self._matched_fields:
            hit.results.fragmenter = WholeFragmenter()
            self._title_highlights = hit.highlights("title", text=self.title)
        else:
            self._title_highlights = None

        if "content" in self._matched_fields:
            hit.results.fragmenter = ContextFragmenter()
            content_ex_tags, _ = Flatnotes.extract_tags(self.content)
            self._content_highlights = hit.highlights(
                "content",
                text=content_ex_tags,
            )
        else:
            self._content_highlights = None

        self._tag_matches = (
            [field[1] for field in hit.matched_terms() if field[0] == "tags"]
            if "tags" in self._matched_fields
            else None
        )

    @property
    def score(self):
        return self._score

    @property
    def title_highlights(self):
        return self._title_highlights

    @property
    def content_highlights(self):
        return self._content_highlights

    @property
    def tag_matches(self):
        return self._tag_matches

    @staticmethod
    def _get_matched_fields(matched_terms):
        """Return a set of matched fields from a set of ('field', 'term') "
        "tuples generated by whoosh.searching.Hit.matched_terms()."""
        return set([matched_term[0] for matched_term in matched_terms])


class Flatnotes(object):
    TAGS_RE = re.compile(r"(?:(?<=^#)|(?<=\s#))\w+(?=\s|$)")
    TAGS_WITH_HASH_RE = re.compile(r"(?:(?<=^)|(?<=\s))#\w+(?=\s|$)")

    def __init__(self, dir: str) -> None:
        if not os.path.exists(dir):
            raise NotADirectoryError(f"'{dir}' is not a valid directory.")
        self.dir = dir

        self.index = self._load_index()
        self.update_index()

    @property
    def index_dir(self):
        return os.path.join(self.dir, ".flatnotes")

    def _load_index(self) -> Index:
        """Load the note index or create new if not exists."""
        index_dir_exists = os.path.exists(self.index_dir)
        if index_dir_exists and whoosh.index.exists_in(
            self.index_dir, indexname=INDEX_SCHEMA_VERSION
        ):
            logger.info("Loading existing index")
            return whoosh.index.open_dir(
                self.index_dir, indexname=INDEX_SCHEMA_VERSION
            )
        else:
            if index_dir_exists:
                logger.info("Deleting outdated index")
                empty_dir(self.index_dir)
            else:
                os.mkdir(self.index_dir)
            logger.info("Creating new index")
            return whoosh.index.create_in(
                self.index_dir, IndexSchema, indexname=INDEX_SCHEMA_VERSION
            )

    @classmethod
    def extract_tags(cls, content) -> Tuple[str, Set[str]]:
        """Strip tags from the given content and return a tuple consisting of:

        - The content without the tags.
        - A set of tags converted to lowercase."""
        content_ex_tags, tags = re_extract(cls.TAGS_RE, content)
        try:
            tags = [tag.lower() for tag in tags]
            return (content_ex_tags, set(tags))
        except IndexError:
            return (content, set())

    def _add_note_to_index(
        self, writer: writing.IndexWriter, note: Note
    ) -> None:
        """Add a Note object to the index using the given writer. If the
        filename already exists in the index an update will be performed
        instead."""
        content_ex_tags, tag_set = self.extract_tags(note.content)
        tag_string = " ".join(tag_set)
        writer.update_document(
            filename=note.filename,
            last_modified=datetime.fromtimestamp(note.last_modified),
            title=note.title,
            content=content_ex_tags,
            tags=tag_string,
        )

    def _get_notes(self) -> List[Note]:
        """Return a list containing a Note object for every file in the notes
        directory."""
        notes = []
        for filepath in glob.glob(os.path.join(self.dir, "**/*" + MARKDOWN_EXT), recursive=True):
            name = strip_ext(os.path.split(filepath)[1])
            name = str(name)
            note = Note(self, name)
            subdirs = os.path.relpath(os.path.dirname(filepath), self.dir)
            note.set_subdirs(subdirs)
            notes.append(note)
        return notes

    def update_index(self, clean: bool = False) -> None:
        """Synchronize the index with the notes directory.
        Specify clean=True to completely rebuild the index"""
        indexed = set()
        writer = self.index.writer()
        if clean:
            writer.mergetype = writing.CLEAR  # Clear the index
        with self.index.searcher() as searcher:
            for idx_note in searcher.all_stored_fields():
                idx_filename = idx_note["filename"]
                idx_filepath = os.path.join(self.dir, idx_filename)
                # Delete missing
                if not os.path.exists(idx_filepath):
                    writer.delete_by_term("filename", idx_filename)
                    logger.info(f"'{idx_filename}' removed from index")
                # Update modified
                elif (
                    datetime.fromtimestamp(os.path.getmtime(idx_filepath))
                    != idx_note["last_modified"]
                ):
                    logger.info(f"'{idx_filename}' updated")
                    self._add_note_to_index(
                        writer, Note(self, strip_ext(idx_filename))
                    )
                    indexed.add(idx_filename)
                # Ignore already indexed
                else:
                    indexed.add(idx_filename)
        # Add new
        for note in self._get_notes():
            if note.filename not in indexed:
                self._add_note_to_index(writer, note)
                logger.info(f"'{note.filename}' added to index")
        writer.commit()

    def get_tags(self):
        """Return a list of all indexed tags."""
        self.update_index_debounced()
        with self.index.reader() as reader:
            tags = reader.field_terms("tags")
            return [tag for tag in tags]

    def pre_process_search_term(self, term):
        term = term.strip()
        # Replace "#tagname" with "tags:tagname"
        term = re.sub(
            self.TAGS_WITH_HASH_RE,
            lambda tag: "tags:" + tag.group(0)[1:],
            term,
        )
        return term

    def search(
        self,
        term: str,
        sort: Literal["score", "title", "last_modified"] = "score",
        order: Literal["asc", "desc"] = "desc",
        limit: int = None,
    ) -> Tuple[SearchResult, ...]:
        """Search the index for the given term."""
        self.update_index()
        term = self.pre_process_search_term(term)
        with self.index.searcher() as searcher:
            # Parse Query
            if term == "*":
                query = Every()
            else:
                parser = MultifieldParser(
                    ["title", "content", "tags"], self.index.schema
                )
                parser.add_plugin(DateParserPlugin())
                query = parser.parse(term)

            # Determine Sort By
            # Note: For the 'sort' option, "score" is converted to None as
            # that is the default for searches anyway and it's quicker for
            # Whoosh if you specify None.
            sort = sort if sort in ["title", "last_modified"] else None

            # Determine Sort Direction
            # Note: Confusingly, when sorting by 'score', reverse = True means
            # asc so we have to flip the logic for that case!
            reverse = order == "desc"
            if sort is None:
                reverse = not reverse

            # Run Search
            results = searcher.search(
                query,
                sortedby=sort,
                reverse=reverse,
                limit=limit,
                terms=True,
            )
            return tuple(SearchResult(self, hit) for hit in results)
