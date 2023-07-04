/**
 *
 * HX711 library for Arduino - example file
 * https://github.com/bogde/HX711
 *
 * MIT License
 * (c) 2018 Bogdan Necula
 *
**/
#include "HX711.h"


// HX711 circuit wiring
const int LOADCELL_DOUT_PIN = 2;
const int LOADCELL_SCK_PIN = 3;


HX711 scale;

void setup() {
  Serial.begin(38400);
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

  Serial.println(scale.read());			// print a raw reading from the ADC

  Serial.println(scale.read_average(20));  	// print the average of 20 readings from the ADC

  Serial.println(scale.get_value(5));		// print the average of 5 readings from the ADC minus the tare weight (not set yet)

  Serial.println(scale.get_units(5), 1);	// print the average of 5 readings from the ADC minus tare weight (not set) divided
						// by the SCALE parameter (not set yet)

  scale.set_scale(2282.f);                      // this value is obtained by calibrating the scale with known weights; see the README for details
  scale.tare();				        // reset the scale to 0

  Serial.println(scale.read());                 // print a raw reading from the ADC

  Serial.println(scale.read_average(20));       // print the average of 20 readings from the ADC

  Serial.println(scale.get_value(5));		// print the average of 5 readings from the ADC minus the tare weight, set with tare()

  Serial.println(scale.get_units(5), 1);        // print the average of 5 readings from the ADC minus tare weight, divided
						// by the SCALE parameter set with set_scale

  Serial.println("Readings:");
}

void loop() {
  Serial.print("first:");
  delay(30);
  Serial.println(scale.get_units(), 1);
  /* delay(30);
  Serial.print("average:");
  delay(30);
  Serial.print(scale.get_units(10), 1); */

  scale.power_down();			        // put the ADC in sleep mode
  delay(200);
  scale.power_up();
}
