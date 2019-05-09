import logging
from unittest import TestCase
from bdl.utils import html_to_unicode
from bdl.tagger import Path, Node, Tree, get_matching_tags, get_tree


log = logging.getLogger(__name__)


class Test(TestCase):

    def test_load(self):
        t = Tree()
        t.load()

    def test_node(self):

        n = Node('louisvuitton', ['louis vuitton', 'vuitton', 'lv'])
        self.assertTrue(n.matches('louis vuitton bag'))
        self.assertTrue(n.matches('vuitton'))
        self.assertFalse(n.matches('gucci bag'))


    def test_path(self):

        lv = Node('louisvuitton', ['louis vuitton', 'vuitton', 'lv'])
        bag = Node('bags', ['bag', 'handbag'])
        fashion = Node('fashion', [])

        p = Path(fashion)
        p.has_child(bag)
        p.has_child(lv)

        self.assertEqual(str(p), 'fashion:bags:louisvuitton')


    def test_tree(self):

        tests = [
            # node name, parents
            ['louisvuitton', 'bags:glasses:shoes', 'fashion', 'fashion:bags:louisvuitton fashion:glasses:louisvuitton fashion:shoes:louisvuitton'],
            ['louisvuittonspeedy', 'louisvuitton', 'bags:fashion', 'fashion:bags:louisvuitton:louisvuittonspeedy fashion:glasses:louisvuitton:louisvuittonspeedy fashion:shoes:louisvuitton:louisvuittonspeedy'],
        ]

        for node_name, node_parents, node_grants, node_paths in tests:

            tree = get_tree()
            n = tree.get_node(node_name)
            log.info("Introspecting node %s" % n)

            # Check node names
            self.assertEqual(n.name, node_name)

            # Check node parents
            names = [p.name for p in n.parents]
            names.sort()
            self.assertEqual(':'.join(names), node_parents)

            # Check node grants
            grants = [p.name for p in n.grants]
            grants.sort()
            self.assertEqual(':'.join(grants), node_grants)

            # Check node paths
            self.assertEqual(len(n.paths), 3)
            paths = [str(p) for p in n.paths]
            paths.sort()
            self.assertEqual(' '.join(paths), node_paths)


    def test_get_matching_tags(self):
        tests = [
            [
                '&auml;kta Louis Vuitton speedy Louis Vuitton speedy 30 i perfekt skick. F&aring;tt den h&auml;rliga m&ouml;rkbruna f&auml;rgen. Knappt anv&auml;nd.',
                ['louisvuitton', 'louisvuittonspeedy', 'path:fashion:bags:louisvuitton:louisvuittonspeedy', 'path:fashion:bags', 'path:fashion:bags:louisvuitton', 'bags', 'path:fashion', 'fashion'],
            ],
            [
                'V&auml;ska Louis Vuitton Louis Vuitton i perfekt skick. Den perfekta v&auml;skan v&auml;skan. F&aring;tt den h&auml;rliga m&ouml;rkbruna f&auml;rgen. Knappt anv&auml;nd.',
                ['louisvuitton', 'path:fashion', 'path:fashion:bags', 'bags', 'path:fashion:bags:louisvuitton', 'fashion'],
            ],
            [
                'LV skor ** Skor, stl. 38, dam ** Nya Louis Vuitton mockasiner.',
                ['louisvuitton', 'path:fashion', 'shoes', 'path:fashion:shoes:louisvuitton', 'path:fashion:shoes', 'fashion'],
            ],
            [
                'Solglas&ouml;gon Gucci Solglas&ouml;gon Gucci, ink&ouml;pta hos optiker i Nice, Frankrike. Skimrande svartbruna med m&ouml;rkt glas. Gucciemblemet i strass p&aring; skalmen. V&auml;ldigt sk&ouml;na och sitter bra p&aring; n&auml;san. Nypris 3 500 kr.',
                ['gucci', 'path:fashion', 'path:fashion:glasses:gucci', 'glasses', 'path:fashion:glasses', 'fashion'],
            ],

            [
                'Solglas&ouml;gon Gucci Solglas&ouml;gon Gucci, ink&ouml;pta hos optiker i Nice, Frankrike. Skimrande svartbruna med m&ouml;rkt glas. Gucciemblemet i strass p&aring; skalmen. V&auml;ldigt sk&ouml;na och sitter bra p&aring; n&auml;san. Nypris 3 500 kr.',
                ['gucci', 'path:fashion', 'path:fashion:glasses:gucci', 'glasses', 'path:fashion:glasses', 'fashion'],
            ],

            [
                'Karmstolar bord pelarbord &aring;ttakantigt bord Charmigt Gustavianskt kaklat bord',
                ['path:antics:gustavian', 'path:antics', 'antics', 'gustavian'],
            ],
            [
                'Rokoko karmstol svenskt tenn',
                ['path:antics:rococo', 'path:antics', 'antics', 'rococo', 'design', 'path:design', 'path:design:svenskttenn', 'svenskttenn'],
            ],
            [
                'Swedese Tree Tree kl&auml;dh&auml;ngare i svart fr&aring;n Swedese.',
                ['path:design', 'design', 'path:design:swedese', 'swedese'],
            ],
            [
                '6 st Sjuan SJUAN 3107 helkl&auml;dda i originaltyg Stolarna &auml;r 15 &aring;r gamla och i bra bruksskick. Annonsen kvar = stolarna kvar. F&ouml;rst till kvarn. Tillverkade av Fritz Hansen, design Arne Jacobsen. Nypris per stol: 8120 kr Mitt pris: 9000 kr för alla 6 stolar',
                ['arnejacobsen', 'path:design', 'path:design:arnejacobsen', 'path:design:fritzhansen', 'fritzhansen', 'design'],
            ],
            [
                'Unik och Rymlig Mulberry axelv&auml;ska 30x40cm i svart l&auml;der och mocka. V&auml;skan ar numrerad. Dustbag medfoljer.',
                ['bags', 'path:fashion', 'path:fashion:bags', 'path:fashion:bags:mulberry', 'fashion', 'mulberry'],
            ],
            [
                'Gutaviansk mattgrupp bord +6 stolar ,sidobird Utdragbar bord med 6stolar i gustaviansk still 1400-1000mm utan il&auml;ggsskivor sideboard sk&auml;nk i samma still och f&auml;rg L1850-DJ 435 H800 M : 5500kr Indisk soffbord300kr ek soffbord 150kr och vinst&auml;ll for 40vin flaskor 1500kr och en tavla for 100kr',
                ['path:antics:gustavian', 'antics', 'gustavian', 'path:antics'],
            ],
            [
                'Michael Kors klocka modell MK6188',
                ['path:fashion:watches', 'fashion', 'path:fashion', 'path:fashion:watches:michaelkors', 'michaelkors', 'watches'],
            ],
        ]

        for text, expected_tags in tests:
            text = html_to_unicode(text)
            tags = get_matching_tags(text)
            log.info("Text [%s..] matches tags: %s" % (text[0:10], tags))

            tags = set(tags)
            expected_tags = set(expected_tags)
            self.assertEqual(tags, expected_tags)
