import unittest
from tracker import check_stock

def page(body):
    return ('<html><head><title>Grand Theft Auto VI White DualSense</title></head>'
            '<body><h1>DualSense GTA VI White Limited Edition</h1><p>'
            + 'Gaming controller information and specifications. ' * 5
            + '</p>' + body + '</body></html>')

class StockTests(unittest.TestCase):
    def test_unavailable_overrides_cart(self):
        self.assertEqual(check_stock("mediamarkt", page("Leider keine Lieferung möglich In den Warenkorb"))[0], "out")
    def test_cart(self):
        self.assertEqual(check_stock("mediamarkt", page("In den Warenkorb"))[0], "possible")
    def test_amazon_unavailable(self):
        self.assertEqual(check_stock("amazon", page('<div id="availability">Derzeit nicht verfügbar</div>'))[0], "out")
    def test_amazon_available(self):
        self.assertEqual(check_stock("amazon", page('<div id="availability">Auf Lager</div>'))[0], "possible")
    def test_preorder_not_enough(self):
        self.assertEqual(check_stock("playstation", page("Vorbestellen"))[0], "unknown")
    def test_wrong_product(self):
        self.assertEqual(check_stock("mediamarkt", "<h1>Andere Kopfhörer</h1>" * 50)[0], "unknown")
    def test_euronics_cart_not_enough(self):
        self.assertEqual(check_stock("euronics", page("In den Warenkorb"))[0], "unknown")
    def test_mueller_out(self):
        self.assertEqual(check_stock("mueller", page("Aktuell nicht lieferbar"))[0], "out")
    def test_okaysoft_preorder(self):
        self.assertEqual(check_stock("okaysoft", page("Vorbestellung - Versand ab: 18.11.2026"))[0], "possible")

    def test_structured_offer(self):
        self.assertEqual(check_stock("playstation", page('<script type="application/ld+json">{"@type":"Product","offers":{"availability":"https://schema.org/InStock"}}</script>'))[0], "possible")

if __name__ == "__main__":
    unittest.main()
