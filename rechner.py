def addiere(a, b):
    return a + b

def subtrahiere(a, b):
    return a - b

def multipliziere(a, b):
    return a * b

def dividiere(a, b):
    if b == 0:
        raise ValueError("Division durch Null ist nicht erlaubt.")
    return a / b

def potenziere(a, b):
    return a ** b

def zeige_menu():
    print("1. Addieren (+)")
    print("2. Subtrahieren (-)")
    print("3. Multiplizieren (*)")
    print("4. Dividieren (/)")
    print("5. Potenzieren (^)")
    print("6. Beenden")

def hole_zahl(prompt):
    """Holt eine gültige Zahl vom Benutzer."""
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Ungültige Eingabe. Bitte geben Sie eine Zahl ein.")

def hole_operation():
    """Holt die gewünschte Operation vom Benutzer."""
    while True:
        zeige_menu()
        auswahl = input("Bitte wählen Sie eine Option (1-6): ").strip()
        if auswahl in ['1', '2', '3', '4', '5', '6']:
            return auswahl
        print("Ungültige Auswahl. Bitte geben Sie 1 bis 6 ein.")

def main():
    """Hauptfunktion des Rechners."""
    print("Willkommen beim Jarvis Test Rechner!")
    
    while True:
        auswahl = hole_operation()
        
        if auswahl == '6':
            print("Programm beendet. Auf Wiedersehen!")
            break
        
        print(f"\nOperation {auswahl}: {'Addieren' if auswahl == '1' else 'Subtrahieren' if auswahl == '2' else 'Multiplizieren' if auswahl == '3' else 'Dividieren' if auswahl == '4' else 'Potenzieren'}")
        
        zahl1 = hole_zahl("Erste Zahl: ")
        zahl2 = hole_zahl("Zweite Zahl: ")
        
        try:
            if auswahl == '1':
                ergebnis = addiere(zahl1, zahl2)
            elif auswahl == '2':
                ergebnis = subtrahiere(zahl1, zahl2)
            elif auswahl == '3':
                ergebnis = multipliziere(zahl1, zahl2)
            elif auswahl == '4':
                ergebnis = dividiere(zahl1, zahl2)
            elif auswahl == '5':
                ergebnis = potenziere(zahl1, zahl2)
            
            print(f"Ergebnis: {ergebnis}\n")
        except ValueError as e:
            print(f"Fehler: {e}\n")

if __name__ == "__main__":
    main()