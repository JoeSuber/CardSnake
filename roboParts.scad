use </home/suber1/openscad/libraries/MCAD/motors.scad>;
use </home/suber1/openscad/libraries/MCAD/involute_gears.scad>;
use <cogs.scad>;

panel_thickness = 7.7;
bin_width = 63.6;
//motor(nema=23);
//mygear();
//rotate([0,45,0])
//    board();
//motorbox();
rotate([90,0,90])
translate([0, 21+88, -77])
    #cardstack();
input_tray();
//roller();
//bearing_block();
//limit_switch();

module input_tray(length=610){
    card_w = bin_width;
    card_h = 88.6;
    motor_face = 56;
    thk = panel_thickness+0.2;
    side_h = card_h+thk+motor_face;
    side_len = length;
    bot_len = 540;
    bot_width = card_w + thk;
    disp = (side_len - bot_len)/2;
    echo("bottom of input tray cut to width =",bot_width);
    for (i=[0,1]){
        mirror([0,i,0])
            translate([0,card_w/2 + thk, 0])
                difference(){
                    board(wdth=side_h, lnth=side_len, kerf=0);
                }                 
    }
    rotate([-90,0,0])
        translate([0,-motor_face, -bot_width/2])
            board(wdth=bot_width, lnth=bot_len, kerf=3.24, ends=20);

    rotate([0,90,0])
        translate([-card_w/2+thk/2, 0, bot_len/2-19.4])
        bearing_block();
    rotate([180,90,0])
        translate([-motor_face/2, 0, bot_len/2-19.4])
        bearing_block();    
    
}
 
module brass(ht=19.5){
     cylinder(r=25.5/2, h=3.2, $fn=64);
     cylinder(r=19.3/2, h=ht, $fn=64);
}

module bolt(length=bin_width+panel_thickness*2+12, shft=6.3/2, hd=12.8/2, thk=panel_thickness){
    echo("bolt has length =",length);
    cylinder(r=shft, h=length, $fn=22);
    cylinder(r=hd, h=6, $fn=6);
    translate([0,0,length-5.9])
        cylinder(r=hd, h=6, $fn=6, center=false);
}

module bearing_block(w=bin_width, ht=19.4, p=panel_thickness){
    l1 = w - p;
    difference(){
        translate([0,0,ht/2]){
            cube([l1-6,w,ht], center=true);
        }
        brass();
        rotate([90,0,0])
        for (i=[1,-1]){
            translate([(l1/2 - 10) *i, ht/2, -(w+p*2+12)/2])
                #bolt();
            echo("bearing block bolts are ",(l1/2 -12) * i, "from centerline");
        }
        rotate([180,0,-90]) translate([17,-11,-10])
            #limit_switch();
    }
}
    
module roller(wdth=62, bearing_d=22.3, bearing_h=8, shaft_d=8.6){
    rad = bearing_d/2;
    ht = wdth/4;
    skinny = rad + 2;
    fat = skinny + 0.6;
    rotate([90,0,0])
        for (i=[0,1]){
            mirror([0, 0, i])
                difference(){
                    union(){
                        cylinder(r=fat, h=ht, $fn=128);
                        translate([0,0,ht])
                            cylinder(r1=fat, r2=skinny, h=ht, $fn=128);
                    }
                    translate([0,0, ht*2 - bearing_h + 0.1]){
                        cylinder(r=rad, h=bearing_h, $fn=96);
                        translate([0,0,-1])
                            cylinder(r=rad-2.7, h=bearing_h+0.7, $fn=64);
                        translate([0,0,-ht*2])
                            cylinder(r=shaft_d/2, h=ht*2+.1, $fn=36);
                    }
               }
        }
 }

module cardstack(quant=1000){
    w=63;
    l=88;
    thk=18.7/60.0;
    rnd = 2.8;
    ht = thk*quant;
    echo("Stack of", quant, "cards =", ht, "mm");
    translate([rnd-(w/2), rnd-(l/2), 0])
    linear_extrude(height = ht, center = false, convexity = 10, twist = 0)
        minkowski(){
            circle(r=rnd, $fn=36);
            square([w-rnd*2, l-rnd*2]);
        }
}
    
module motor(nema=17, h=20, slide=18){
linear_extrude(height = h, center = true, convexity = 10, twist = 0)
    stepper_motor_mount(nema, slide_distance=slide, mochup=true, tolerance=0.2);
}

module motorbox(nema=23, cogs=true, posts=panel_thickness){
    if (nema==23){
        h1 = 60;
        h2 = 5.05;
        outside = 56;
        narrow = 38;
        rad = 4.34;
        mnt = 47/2;
        shaft_h = 22;
        cog_h = 15;
        translate([0, 0, -(h1+h2)]){
            
            linear_extrude(height = h1, center=false, convexity=10)
                union(){
                    for (i=[0,90]){
                        rotate([0,0,i])
                            square([outside, narrow], center=true);
                    }
                }
            translate([0, 0, h1])
            linear_extrude(height = h2, center=false, convexity=10)
                minkowski(){
                    square([outside-(rad*2), outside-(rad*2)], center=true);
                    circle(r=rad);
                }
            translate([0, 0, h1+h2]){
                cylinder(r=narrow/2, h=2, $fn=36);
                cylinder(r=7.95*0.5, h=shaft_h, $fn=12);
                translate([0,0,shaft_h - cog_h])
                    mycog(wheel_height=cog_h);
            }
            translate([outside/2+5, 0, 11.5/2]){
                cube([10.1, 21, 11.5], center=true);
            }
            translate([0, 0, 11.5/2]){
            for (i=[1,-1], j=[1,-1]){
                translate([mnt*i, mnt*j, h1+h2/2])
                    cylinder(r=2, h=posts*2 + h2, center=true,$fn=12);
                }
            }
        }
    }
}
                 
module mygear(teeth=31){
    test_double_helix_gear(teeth=teeth);
}

module limit_switch(wirelen=40){
    w = 7;
    l = 20.5;
    ht = 11;
    peg_w = 3.5;
    peg_d = 2.7;
    cube([w, l, ht]);
    for (i=[2.5, 11.3, 18.6]) {
        translate([(w/2 - peg_w/2), i, -wirelen])
            cube([peg_w, peg_d, wirelen]);
    }
}

module board(thk=panel_thickness, wdth=175, lnth=500, ends=2, kerf=8){
    motor_ht = 65/2;
    rotate([90,0,0])
        translate([-lnth/2,0,0])
            difference(){
                cube([lnth, wdth, thk], center=false);
                translate([ends,wdth/2 - kerf/2,0])
                    cube([lnth-ends*2, kerf, thk+0.1]);
                translate([motor_ht, 0, thk/2])
                    #cube([thk, wdth, thk/2]);
            }
}