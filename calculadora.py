class Calculadora:
    def __init__(self):
        self.historial = []

    def _registrar(self, operacion, resultado):
        self.historial.append(f"{operacion} = {resultado}")

    def sumar(self, a, b):
        resultado = a + b
        self._registrar(f"{a} + {b}", resultado)
        return resultado

    def restar(self, a, b):
        resultado = a - b
        self._registrar(f"{a} - {b}", resultado)
        return resultado

    def multiplicar(self, a, b):
        resultado = a * b
        self._registrar(f"{a} * {b}", resultado)
        return resultado

    def dividir(self, a, b):
        if b == 0:
            raise ValueError("No se puede dividir entre cero")
        resultado = a / b
        self._registrar(f"{a} / {b}", resultado)
        return resultado

    def potencia(self, base, exponente):
        resultado = base ** exponente
        self._registrar(f"{base} ^ {exponente}", resultado)
        return resultado

    def raiz_cuadrada(self, a):
        if a < 0:
            raise ValueError("No se puede calcular la raíz cuadrada de un número negativo")
        resultado = a ** 0.5
        self._registrar(f"√{a}", resultado)
        return resultado

    def ver_historial(self):
        if not self.historial:
            print("El historial está vacío.")
        else:
            print("\n--- Historial de operaciones ---")
            for i, entrada in enumerate(self.historial, 1):
                print(f"  {i}. {entrada}")
            print("--------------------------------")

    def limpiar_historial(self):
        self.historial.clear()
        print("Historial limpiado.")


def menu():
    calc = Calculadora()
    opciones = {
        "1": "Sumar",
        "2": "Restar",
        "3": "Multiplicar",
        "4": "Dividir",
        "5": "Potencia",
        "6": "Raíz cuadrada",
        "7": "Ver historial",
        "8": "Limpiar historial",
        "9": "Salir",
    }

    while True:
        print("\n====== Calculadora POO ======")
        for clave, nombre in opciones.items():
            print(f"  {clave}. {nombre}")
        print("=============================")

        opcion = input("Seleccione una opción: ").strip()

        if opcion == "9":
            print("¡Hasta luego!")
            break

        elif opcion in ("1", "2", "3", "4", "5"):
            try:
                a = float(input("Ingrese el primer número: "))
                b = float(input("Ingrese el segundo número: "))
                if opcion == "1":
                    print(f"Resultado: {calc.sumar(a, b)}")
                elif opcion == "2":
                    print(f"Resultado: {calc.restar(a, b)}")
                elif opcion == "3":
                    print(f"Resultado: {calc.multiplicar(a, b)}")
                elif opcion == "4":
                    print(f"Resultado: {calc.dividir(a, b)}")
                elif opcion == "5":
                    print(f"Resultado: {calc.potencia(a, b)}")
            except ValueError as e:
                print(f"Error: {e}")

        elif opcion == "6":
            try:
                a = float(input("Ingrese el número: "))
                print(f"Resultado: {calc.raiz_cuadrada(a)}")
            except ValueError as e:
                print(f"Error: {e}")

        elif opcion == "7":
            calc.ver_historial()

        elif opcion == "8":
            calc.limpiar_historial()

        else:
            print("Opción no válida. Intente de nuevo.")


if __name__ == "__main__":
    menu()
