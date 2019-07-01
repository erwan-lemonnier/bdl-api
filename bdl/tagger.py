import os
import logging
import re
import string
from bdl.utils import html_to_unicode


log = logging.getLogger(__name__)


DIR_NODES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'etc', 'nodes')


def text_to_words(s):
    """Take a unicode encoded text and split it into a list of words"""
    s = s.lower()
    regex = re.compile(r'[%s%s%s]+' % (re.escape(string.punctuation), string.digits, string.whitespace))
    l = regex.split(s)
    l = [ss for ss in l if ss]
    return l


class Keyword:
    """A keyword to match against any text. A keyword may match only against one
    given language (self.language is set), or against all languages
    (self.language is None)
    """

    def __init__(self, word):
        self.language = None
        self.word = word

        if re.match("^[a-z]{2}:", word):
            language, word = word.split(':', 1)
            self.language = language
            self.word = word

    def match(self, text, language):
        """Check if this text matches with this keyword"""
        assert text
        assert language
        # log.debug("Matching [%s]/[%s] against %s" % (language, text, self))

        text = text.lower()

        if self.language and self.language != language:
            return False

        # Match words exactly
        return " %s " % self.word in " %s " % text

    def __str__(self):
        return '%s[%s]' % (self.word, self.language if self.language else '')


class KeywordList:
    """A list of keywords to match against any text. The keywords are parsed from
    a file, which may optionally contain the following header attributes:

    # parents: tag1, tag2...     -> parent tags under which matching items may be found
    # grants: tag1, tag2...      -> tags to attach to any matching item
    # name: This That            -> name to show in the frontend for this category
    keyword1
    keyword2  -> general keywords, matching whatever the language
    en:keyword3   -> keyword to match only if announce is in english
    <locale>:keyword4

    Thanks to those header attributes, keyword lists may be linked to each
    other to form a tree of nodes, in which the top nodes are the top
    categories classifying the matching item.

    """

    def __init__(self, path):
        log.info("Loading keyword list from %s" % path)

        self.name = path.split('/')[-1].replace('.html', '').replace('.txt', '')
        self.translation = self.name
        self.is_html = True if path.endswith('.html') else False
        self.parent_tags = []
        self.grant_tags = []
        self.keywords = []

        s = open(path).read()
        for l in s.splitlines():
            if l.startswith('#'):
                if l.startswith('# parents: '):
                    tags = l.split(':')[1].split(',')
                    tags = [ss.strip() for ss in tags]
                    self.parent_tags = tags
                elif l.startswith('# grants: '):
                    tags = l.split(':')[1].split(',')
                    tags = [ss.strip() for ss in tags]
                    self.grant_tags = tags
                elif l.startswith('# name: '):
                    self.translation = l.split(':')[1].strip()
                else:
                    raise Exception("Keyword file has borked header: %s" % path)
            else:
                l = l.lower()
                if self.is_html:
                    l = html_to_unicode(l)
                l = l.strip()
                if l:
                    self.keywords.append(Keyword(l))

    def match(self, text, language):
        assert language
        # log.debug("Matching [%s]/[%s] against %s" % (language, text, self))
        text = text.lower()
        for w in self.keywords:
            if w.match(text, language):
                log.debug("Item matches [%s] in list %s" % (w, self.name))
                return True
        return False

    def __str__(self):
        return "<KeywordList '%s': %s>" % (
            self.filename,
            ' '.join([str(w) for w in self.keywords]),
        )


class Node:

    # Nodes are interconnected keyword lists, forming a tree with multiple roots. Attributes:
    #
    # parents: list of parent nodes
    # paths:   pathes from this node to the various root categgories they match
    # grants:  list of nodes to grant a matching text

    def __init__(self, name, kwl):
        assert type(name) is str
        assert type(kwl) is KeywordList

        self.name = name
        self.translation = kwl.translation
        self.keywords = kwl.keywords
        self.parents = []
        self.paths = []
        self.grants = []

    def set_paths(self, paths):
        assert type(paths) is list
        self.paths = paths

    def set_parents(self, nodes):
        assert type(nodes) is list
        self.parents = nodes

    def set_grants(self, nodes):
        assert type(nodes) is list
        self.grants = nodes

    def match(self, text, language):
        """Return true if this node matches that string"""
        assert type(text) is str
        assert language

        text = " %s " % text.lower()

        for w in self.keywords:
            if w.match(text, language):
                log.debug("Item matches [%s] in node %s" % (w, self.name))
                return True

        return False

    def __str__(self):
        return "<Node %s: Parents[%s] Paths[%s]>" % (
            self.name,
            ','.join([n.name for n in self.parents]),
            ','.join([str(p) for p in self.paths])
        )


class Path:

    def __init__(self, node):
        assert type(node) is Node
        self.nodes = [node]

    def has_child(self, node):
        assert type(node) is Node
        self.nodes.append(node)
        return self

    def __str__(self):
        return ':'.join([n.name for n in self.nodes])


class Tree:

    def __init__(self):
        self.all_nodes = {}

    def get_all_nodes(self):
        return self.all_nodes.values()

    def get_node(self, name):
        if name in self.all_nodes:
            return self.all_nodes[name]
        return None

    def _get_paths(self, node):
        # log.debug("Finding paths towards %s" % node)
        if len(node.parents) == 0:
            return [Path(node)]
        else:
            paths = []
            for parent in node.parents:
                # log.debug("Looking at parent %s" % parent)
                parent_paths = self._get_paths(parent)
                # log.debug("Parent has paths: %s" % ' '.join([str(p) for p in parent_paths]))
                for p in parent_paths:
                    p.has_child(node)
                    paths.append(p)
            # log.info("This node has paths: %s" % (' '.join([str(p) for p in paths])))
            return paths

    def load(self):
        """Load all tree nodes and their relations from tag files"""

        self.all_nodes = {
            # name: Node
        }

        # node parents and grants
        node_parents = {}
        node_grants = {}

        # Step 1: load all nodes from tag files
        for filename in sorted(os.listdir(DIR_NODES)):

            if not filename.endswith(".html"):
                continue

            # log.debug("Loading tags from %s" % filename)

            kwl = KeywordList(DIR_NODES + '/' + filename)

            node = Node(kwl.name, kwl)
            self.all_nodes[node.name] = node

            node_parents[kwl.name] = kwl.parent_tags
            node_grants[kwl.name] = kwl.grant_tags

            # log.info("Loaded node [%s] %s" % (node.name, parent_names))

        # Step: 1.5 -> sanity checking
        for node_names in node_parents.values():
            for name in node_names:
                if name not in self.all_nodes:
                    raise Exception("Can't find parent node %s" % name)

        for node_names in node_grants.values():
            for name in node_names:
                if name not in self.all_nodes:
                    raise Exception("Can't find granted node %s" % name)

        # for name in self.all_nodes.keys():
        #     log.debug("Checking has translation for %s" % name)
        #     s = translate('CATEGORY_%s' % name.upper(), 'en')
        #     if 'translation' in s:
        #         raise Exception("Missing translation for name %s" % name)

        # Step 2: connect those nodes into a tree of pathes
        for node in self.all_nodes.values():
            parents = []
            if node_parents[node.name]:
                for name in node_parents[node.name]:
                    if name in self.all_nodes:
                        parents.append(self.all_nodes[name])
            node.set_parents(parents)

        # Step 3: set which nodes are auto-granted on matching
        for node in self.all_nodes.values():
            if node_grants[node.name]:
                grants = []
                for name in node_grants[node.name]:
                    grants.append(self.all_nodes[name])
                # log.debug("Node %s auto-grants %s" % (node, ' '.join([n.name for n in grants])))
                node.set_grants(grants)

        # Step 4: map all paths for every node
        for node in self.all_nodes.values():
            # log.debug("Mapping all paths towards %s" % node)
            paths = self._get_paths(node)
            # log.debug("Node %s has paths %s" % (node, ' '.join([str(p) for p in paths])))
            node.set_paths(paths)


tree = Tree()
tree.load()

def get_tree():
    global tree
    return tree

def get_matching_tags(text, language):
    """Find all the tags and paths that apply to this text"""

    assert text
    assert language

    # log.debug('TAG MATCHER: Finding tags matching [%s..]' % (text[0:10]))

    # First, split the text into words for exact word matching,
    # then back into a string
    words = text_to_words(text)
    text = ' '.join(words)

    # We'll keep track of paths and tags
    paths = set()
    tags = set()

    matching_nodes = {
        # name: node
    }

    # Find all nodes
    for node in tree.get_all_nodes():
        if node.match(text, language):
            # log.debug('TAG MATCHER: Text [%s] matches node %s' % (text[0:10], node))
            matching_nodes[node.name] = node
            if node.grants:
                for n in node.grants:
                    matching_nodes[n.name] = n

    # log.debug('TAG MATCHER: Text [%s..] matches NODE: %s' % (text[0:10], ' '.join([str(n) for n in matching_nodes.values()])))

    # Now find matching paths
    for node in matching_nodes.values():
        for path in node.paths:
            # Do all the nodes in this path match?

            # It's enough if match the two last nodes
            path_matches = True
            for n in path.nodes:
                if n.name not in matching_nodes:
                    # log.debug("TAG MATCHER: Does not match node %s" % n)
                    path_matches = False
                    break

            if path_matches:
                # log.debug('TAG MATCHER: Text [%s] matches PATH %s' % (text[0:10], path))
                paths.add(path)
                tags.add('path:%s' % str(path))

    # Now extract all individual tags from matching paths
    for path in paths:
        for node in path.nodes:
            tags.add(node.name)

    tags = tags
    log.debug('Text [%s..] matches tags: %s' % (text[0:20], ' '.join(list(tags))))
    return sorted(list(tags))
