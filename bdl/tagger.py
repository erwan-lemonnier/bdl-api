import os
import logging
import re
import string
from bdl.utils import html_to_unicode


log = logging.getLogger(__name__)


DIR_TAGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'etc', 'tags')


def text_to_words(s):
    """Take a unicode encoded text and split it into a list of words"""
    s = s.lower()
    regex = re.compile(r'[%s%s%s]+' % (re.escape(string.punctuation), string.digits, string.whitespace))
    l = regex.split(s)
    l = [ss for ss in l if ss]
    return l


class Keyword:
    # A keyword to match against

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
        log.debug("Matching [%s]/[%s] against %s" % (language, text, self))

        if self.language and self.language != language:
            return False

        # Match words exactly
        return " %s " % self.word in ' %s ' % text

    def __str__(self):
        return '%s[%s]' % (self.word, self.language if self.language else '')


class Node:

    # A tag file (=Node) has the following structure:
    #
    # # parents: the tag nodes right over whatever matches any of those keywords
    # # grants: the tags to assign to whatever matches any of those keywords
    # keyword1
    # keyword2  -> general keywords, matching whatever the language
    # en:keyword3   -> keyword to match only if announce is in english
    # <locale>:keyword4

    def __init__(self, name, match_words=[]):
        assert type(name) is str
        assert type(match_words) is list

        self.name = name
        self.keywords = [Keyword(w) for w in match_words]
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

    def matches(self, text, language='en'):
        """Return true if this node matches that string"""
        assert type(text) is str

        text = " %s " % text.lower()

        for w in self.keywords:
            if w.match(text, language):
                log.debug("Item matches [%s] in node %s" % (w, self.name))
                return True

        return False

    def __str__(self):
        return "Node:%s:Parents[%s]Paths[%s]" % (
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
        for filename in sorted(os.listdir(DIR_TAGS)):

            if not filename.endswith(".html"):
                continue

            # log.debug("Loading tags from %s" % filename)

            s = open(DIR_TAGS + '/' + filename).read()

            match_words = []
            name = filename.split('/')[-1].replace('.html', '')
            parent_names = []
            grants_names = []

            for l in s.splitlines():
                if l.startswith('#'):
                    if l.startswith('# parents: '):
                        parent_names = l.split(':')[1].split(',')
                        parent_names = [ss.strip() for ss in parent_names]
                    elif l.startswith('# grants: '):
                        grants_names = l.split(':')[1].split(',')
                        grants_names = [ss.strip() for ss in grants_names]
                    else:
                        raise Exception("File name %s is badly formatted" % filename)
                else:
                    l = l.lower()
                    l = html_to_unicode(l)
                    l = l.strip()
                    if l:
                        match_words.append(l)

            node = Node(name, match_words)
            self.all_nodes[node.name] = node

            node_parents[name] = parent_names
            node_grants[name] = grants_names

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

def get_matching_tags(text):
    """Find all the tags and paths that apply to this text"""

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
        if node.matches(text):
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
    return list(tags)
