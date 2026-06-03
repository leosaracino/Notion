import unittest
from decimal import Decimal

from notion_portfolio.automation import _fator_de_cdi, _ler_valor_aplicado, calcular_ir_iof


class CalculosFinanceirosTest(unittest.TestCase):
    def test_ir_regressivo_e_iof(self) -> None:
        ganho = Decimal("100.00")

        ir, iof = calcular_ir_iof(ganho, 10)
        self.assertEqual(ir, Decimal("22.50000"))
        self.assertEqual(iof, Decimal("66.0000"))

        ir, iof = calcular_ir_iof(ganho, 31)
        self.assertEqual(ir, Decimal("22.50000"))
        self.assertEqual(iof, Decimal("0"))

        ir, _ = calcular_ir_iof(ganho, 400)
        self.assertEqual(ir, Decimal("17.50000"))

        ir, _ = calcular_ir_iof(ganho, 800)
        self.assertEqual(ir, Decimal("15.0000"))

    def test_ler_valor_aplicado_por_mercado(self) -> None:
        props = {
            "Valor Aplicado R$": {"number": 100.0},
            "Valor Aplicado  $": {"number": 20.0},
        }

        self.assertEqual(_ler_valor_aplicado(props, "BR"), (100.0, "Valor Aplicado R$"))
        self.assertEqual(_ler_valor_aplicado(props, "US"), (20.0, "Valor Aplicado  $"))

    def test_fator_cdi_usa_percentual_do_notion(self) -> None:
        fator_100_cdi = _fator_de_cdi(Decimal("13.65"), 1.0)
        fator_110_cdi = _fator_de_cdi(Decimal("13.65"), 1.1)

        self.assertGreater(fator_100_cdi, Decimal("1"))
        self.assertGreater(fator_110_cdi, fator_100_cdi)


if __name__ == "__main__":
    unittest.main()
