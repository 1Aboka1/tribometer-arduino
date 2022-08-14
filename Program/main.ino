#include "HX711.h"
#include <LiquidCrystal.h>

// HX711 circuit wiring
const int LOADCELL_DOUT_PIN = 7;
const int LOADCELL_SCK_PIN = 6;

LiquidCrystal lcd(12, 11, 10, 5, 4, 3, 2);
HX711 scale;

void setup() {
    lcd.begin(16, 2);
    lcd.setCursor(1, 0);
    lcd.print("HX711");
    delay(500);
    lcd.clear();
    lcd.setCursor(1, 0);
    pinMode(9, OUTPUT);
    analogWrite(9, 50);
    lcd.print("Initializing the scale");
    lcd.clear();

    // Initialize library with data output pin, clock input pin and gain factor.
    // Channel selection is made by passing the appropriate gain:
    // - With a gain factor of 64 or 128, channel A is selected
    // - With a gain factor of 32, channel B is selected
    // By omitting the gain factor parameter, the library
    // default "128" (Channel A) is used here.
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

    scale.set_scale(2280.f);                      // this value is obtained by calibrating the scale with known weights; see the README for details
    scale.tare();				        // reset the scale to 0


    // lcd.print(scale.read());                 // print a raw reading from the ADC

    // lcd.print("read average: ");
    // lcd.print(scale.read_average(20));       // print the average of 20 readings from the ADC

    // lcd.print("get value: ");
    // lcd.print(scale.get_value(5));		// print the average of 5 readings from the ADC minus the tare weight, set with tare()

    // lcd.print("get units: ");
    // lcd.print(scale.get_units(5), 1);        // print the average of 5 readings from the ADC minus tare weight, divided
    //           // by the SCALE parameter set with set_scale

    // lcd.print("Readings:");
}

void loop() {
	lcd.clear();
	lcd.setCursor(0, 0);
	lcd.print("reading: ");
	lcd.print(scale.get_units(), 1);
	lcd.setCursor(0, 1);
	lcd.print("average: ");
	lcd.print(scale.get_units(10), 1);

	scale.power_down();			        // put the ADC in sleep mode
	delay(2000);
	scale.power_up();
	lcd.clear();
}