// This file is for use with the new (in April, 2016) MarlinDev configuration system
// it goes under the 'custom' directory of the cloned repo in a dir labeled like '4faf695a'.
// The repo itself should be put in:  ~/Arduino/libraries/
/*
// to change these const bool items I still had to directly modify:
// ~/Arduino/libraries/MarlinDev/configurations/transitional_default_configurations/ramps/configuration.h

const bool X_MIN_ENDSTOP_INVERTING = true; // set to true to invert the logic of the endstop.
const bool Y_MIN_ENDSTOP_INVERTING = true; // set to true to invert the logic of the endstop.
const bool Z_MIN_ENDSTOP_INVERTING = true; // set to true to invert the logic of the endstop.
const bool X_MAX_ENDSTOP_INVERTING = true; // set to true to invert the logic of the endstop.
const bool Y_MAX_ENDSTOP_INVERTING = true; // set to true to invert the logic of the endstop.
const bool Z_MAX_ENDSTOP_INVERTING = true; // set to true to invert the logic of the endstop.
const bool Z_MIN_PROBE_ENDSTOP_INVERTING = true; // set to true to invert the logic of the endstop.

// to use this file the following lines are modified in 'FirmwareCustomization.h'

#if 1

  // You can obtain a unique id by visiting https://www.uuidgenerator.net/version4

  #define  SPECIFIC_PRINTER_ID 4faf695a
  #include "configurations/custom/4faf695a/Customization.h"

#endif
*/

#define CUSTOMIZATION_H
#define UUID "4faf695a-cb35-4e2b-b5af-62107b61823f"
#define STRING_CONFIG_H_AUTHOR "Joe Suber"
#define CUSTOM_MACHINE_NAME "Magic Robot"

// fake out the temp monitor so that we can do "print" moves without restrictions
#define DUMMY_THERMISTOR_998_VALUE 230
#define DUMMY_THERMISTOR_999_VALUE 100
#define TEMP_SENSOR_0 998
#define TEMP_SENSOR_BED 999

#define DISABLE_Y true
#define DISABLE_Z true

#define INVERT_Z_DIR true

#define X_MAX_POS 110
#define Y_MAX_POS 210
#define Z_MAX_POS 254

#define HOMING_FEEDRATE {50*60, 7*60, 12*60, 0}  // set the homing speeds (mm/min)

#define DEFAULT_AXIS_STEPS_PER_UNIT   {100,13589,1297,500}  // steps per unit (mm)
#define DEFAULT_MAX_FEEDRATE          {600,9,17,25}    // (mm/sec){600,9,17,25}
#define DEFAULT_MAX_ACCELERATION      {100,150,150,10000}    // X, Y, Z, E maximum start speed for accelerated moves.

#define DEFAULT_ACCELERATION          3000    // X, Y, Z and E acceleration in mm/s^2 for printing moves
#define DEFAULT_RETRACT_ACCELERATION  3000    // E acceleration in mm/s^2 for retracts
#define DEFAULT_TRAVEL_ACCELERATION   3000    // X, Y, Z acceleration in mm/s^2 for travel (non printing) moves

// The speed change that does not require acceleration (i.e. the software might assume it can be done instantaneously)
#define DEFAULT_XYJERK                2.0    // (mm/sec)
#define DEFAULT_ZJERK                 0.4     // (mm/sec)

#define ABS_PREHEAT_HOTEND_TEMP 230
#define ABS_PREHEAT_HPB_TEMP 100

#define NUM_SERVOS 1 // Servo index starts with 0 for M280 command
// Servo Endstops
// Use M851 to set the Z probe vertical offset from the nozzle. Store that setting with M500.
//#define X_ENDSTOP_SERVO_NR 1
//#define Y_ENDSTOP_SERVO_NR 2
#define Z_ENDSTOP_SERVO_NR 0
#define SERVO_ENDSTOP_ANGLES {{0,0}, {0,0}, {57,120}} // X,Y,Z Axis Extend and Retract angles
// With this option servos are powered only during movement, then turned off to prevent jitter.
#define DEACTIVATE_SERVOS_AFTER_MOVE
#if ENABLED(DEACTIVATE_SERVOS_AFTER_MOVE)
  #define SERVO_DEACTIVATION_DELAY 350
#endif

// below are items from configuration_adv.h:
#define Z_HOME_BUMP_MM 5
#define HOMING_BUMP_DIVISOR {2, 2, 2}  // Re-Bump Speed Divisor (Divides the Homing Feedrate)

// I guess includes go at the end?
#include "configurations/transitional_default_configurations/ramps/Configuration.h"
#include "configurations/transitional_default_configurations/ramps/Configuration_adv.h"