use </home/suber1/openscad/libraries/MCAD/motors.scad>;
use </home/suber1/openscad/libraries/MCAD/involute_gears.scad>;
use </home/suber1/openscad/libraries/cogs.scad>;

panel_thickness = 7.7;
bin_width = 63.6;
bearing_block_thk = 19.4;
cog_to_cog_center = 63;
cogs_fudge = 3;
motor_face = 56;
//motor(nema=23);
//mygear();
//rotate([0,45,0])
//    board();
//motorbox();
rotate([90,0,90])
translate([0, 21+88, -77])
    #cardstack();
//input_tray();
//check();
//travler();
pusher();
//roller();
//bearing_block();
//limit_switch();
//m3();
//motor_mount();

module input_tray(length=650){
    card_w = bin_width;
    card_h = 88.6;
    motor_face = motor_face;
    thk = panel_thickness+0.2;
    side_h = card_h+thk+motor_face;
    side_len = length;
    bot_len = length - 59;
    motor_shaft = 22;
    motor_h = 65.05+motor_shaft;
    roller_rad = 13.75;
    block_thk = bearing_block_thk;
    bot_width = card_w + thk;
    disp = (side_len - bot_len)/2;
    high_hole = motor_face*2;
    low_rollers = (bot_len/2 + roller_rad + 4);
    echo("bottom of input tray cut to width =",bot_width);
    echo("sides are ",side_h, " wide and ", length, " long");
    
    //  
    for (i=[0,1]){
        mirror([0,i,0])
            translate([0,card_w/2 + thk, 0])
                difference(){
                    board(wdth=side_h, lnth=side_len, kerf=0);
                }              
    }
    
    // bottom with slit
    rotate([-90,0,0])
        translate([motor_h/2,-motor_face, -bot_width/2])
            board(wdth=bot_width, lnth=bot_len-motor_h, kerf=3.24, ends=20);
    
    // bearing blocks
        // front
    echo("front bearing block center on x,y = ",bot_len/2-block_thk/2, -card_w/2+thk/2);
    rotate([0,90,0])
        translate([-card_w/2+thk/2, 0, bot_len/2-block_thk])
        #bearing_block();
    echo("back bearing block center on x,y = ",bot_len/2-block_thk*1.5, -motor_face/2);
    rotate([180,90,0])
        translate([-motor_face/2, 0, bot_len/2-block_thk*2])
        bearing_block();
    
    // bottom 2 belt rollers
    echo("low rollers, from center=", low_rollers, " and from bottom =", roller_rad );
    for (i=[-1,1]){
        translate([i*low_rollers, 0, roller_rad])
            roller(showshaft=1);
    }
    // front top roller
    echo("front-top-roller, (x,y)= ",bot_len/2 + roller_rad, roller_rad+36.1);
    translate([bot_len/2 + roller_rad, 0, roller_rad+36.1])
       #roller(showshaft=1);
    // back high roller
    echo("back high roller(x,y)= ", -bot_len/2 - roller_rad, high_hole);
    translate([-bot_len/2 - roller_rad, 0, high_hole])
       #roller(showshaft=1);
    // front high roller
     echo("front high roller(x,y)= ", -bot_len/2 + roller_rad + motor_h + 1, high_hole);
    translate([-bot_len/2 + roller_rad + motor_h + 1, 0, high_hole])
       #roller(showshaft=1);
    // deck roller
    echo("deck roller is just below at:",motor_face+thk+roller_rad+1);
    translate([-bot_len/2 + roller_rad + motor_h + 1, 0, motor_face+thk+roller_rad+1])
       #roller(showshaft=1);
    // motor
    translate([-bot_len/2 + motor_shaft, 0, motor_face*1.5 + thk]) rotate([0,90,-180]) 
        motorbox();
    // cogwheel centers indicator
    for (i=[0,1]){
    translate([-bot_len/2+(i*33)-5,0,card_w/2-thk/2])
        #cylinder(r=1, h=cog_to_cog_center);
    }
    translate([-bot_len/2-3,0,card_w/2-thk/2]) rotate([0,90,0])
        mybigcog(wheel_height=22);
    // motor mount
    echo("motor mount center at x, y", -bot_len/2+motor_shaft+5.1,motor_face*1.5 + thk);
    translate([-bot_len/2+motor_shaft,0,motor_face*1.5 + thk]) rotate([0,90,0])
        motor_mount();
    // rails
    railroad();
    belt_calc();
}
 
module check(yforward=79.2/2){
    measures=[285.8, 285.8-(274.6/2), 285.8-274.6, -266.4,313.25,-313.25,309.25,-309.25, -193.76, -273.5+5.1];
    ymeasures=[28-17.95, 28+17.95, 13.75, 49.85, 112, 78.65, 91.9, 91.9+29.8, 91.9-29.8];
    echo("ymeasures =",ymeasures);
    echo("xmeasures =",measures);
    side_h=153;
    for (i=measures){
        translate([i, yforward,0])
            #cylinder(r=.5, h=side_h);
    }
    for (i=ymeasures){
        translate([0, yforward, i])
            rotate([0,90,0])
            #cylinder(r=.5, h=650, center=true);
    }  
}

module belt_calc(){
    belt=1440;
    r1=46.15;
    roundpart=r1*2*3.141592654;
    betweenpart= (belt - roundpart) /2;
    echo("from center to center, belt stretches:", betweenpart);
}
    
module railroad(x1=285.8, y1=45.95, wheelrad=46.15, gap=45){
    //module mybiggercog() must determine wheelrad to get evenly spaced cogs
    echo("back sprocket",-wheelrad*4-2*gap,"behind front");
            translate([x1, 79.2/2, y1]) rotate([-90,0,0]) 
                for (i=[0, -wheelrad*4-(2*gap)]){
                    translate([i, 0, 8])
                        sprocket(rad=wheelrad, ht=10.2, bearing_rad=11.2, ang=-180);
                }
}

module sprocket(rad=46.15, ht=10.2, bearing_rad=11.2, ang=-90, with_arm=0){
    // module mybiggercog() must determine wheelrad to get evenly spaced cogs
    support_offset_angle=180;
    belt_width = 7.2;
    edges = (ht - belt_width) / 2;
    swing_len = rad - bearing_rad - 2.4;
    echo("arm travel through 180 deg = ", swing_len*2);
    difference(){
        union(){
            mybiggercog(edges=edges, cogh=belt_width, outside_rad=rad);
            if (with_arm==1){
            translate([(swing_len)*cos(ang), (swing_len)*sin(ang), -4]){
                cube([25, 24, 8], center=true);
                translate([0, -24, 0])
                    cube([180, 24, 8], center=true);
                }
            }
        }
        //center axis bearing cutout
        cylinder(r=bearing_rad - 2.5, h=ht*2, center=true);
        cylinder(r=bearing_rad, h=8, $fn=48);
        
        // arm axis attachment w/ bearing
        for (i=[0:60:360]){
            translate([swing_len*cos(ang+i), swing_len*sin(ang+i), 0]){
                cylinder(r=bearing_rad - 2.5, h=ht*2, $fn=16);
                translate([0,0,0])
                    cylinder(r=bearing_rad, h=8, $fn=48);
            }
        }
    }
}

module nut_on_thread(nut_rad=21.8/2, rod_rad=12.8/2){
    cylinder(r=rod_rad, h=90, $fn=24, center=true);
    cylinder(r=nut_rad, h=12.6, $fn=6, center=true);
}
    
module bolt(ht=15, nut_ht=15){
    translate([0,0,-ht/2]){
        cylinder(h=ht, r=6.6/2, $fn=12);
        cylinder(h=4, r=12.7/2, $fn=6);
        translate([0,0,nut_ht-5.45])
            cylinder(h=5.6, r=12.7/2, $fn=6);
    }
}

module travler(center2slot=motor_face/2, plate_thick=2, nut_rad=21.8/2, border=2, along_rod=35){
    difference(){
        translate([center2slot/2 - nut_rad/2 - border/2,0,along_rod/2]){
            cube([center2slot+nut_rad+border, nut_rad*2+border, along_rod], center=true);
        }
        translate([0,0,along_rod/2]){
            #nut_on_thread(nut_rad=nut_rad);
        }
        translate([center2slot/2, 0, along_rod/2]){
            cube([center2slot, plate_thick+0.1, along_rod], center=true);
        }
        for (i=[1.3,4.2]){
            translate([center2slot/2+6, (nut_rad*2+border)/2, along_rod/i]){
                 rotate([90, 0, 0])
                    #bolt(ht=1);
            }
        }
    }
}

module pusher(plate_thick=3, plate_width=35, face_thk=3, face_wdth=47){
    difference(){
        cube([plate_width+face_thk*2, face_wdth, 70]);
        // slot runner hole
        translate([face_thk, (face_wdth-plate_thick)/2, 0])
            cube([plate_width, plate_thick, 50]);
        // tighteners
        for (i=[face_wdth-(face_wdth*0.25), face_wdth*0.25]){
            translate([0,i, 30])
                rotate([0,90,0])
                    #bolt(ht=55, nut_ht=55);
        }
        for (i=[0, face_wdth-8]){
            translate([12, i, 0])
                cube([0.6,8,70]);
        }
    }
}

module brass(ht=bearing_block_thk+0.1){
     cylinder(r=25.9/2, h=3.2, $fn=64);
     cylinder(r=19.6/2, h=ht, $fn=64);
}

module bearing_sleeve(){
    difference(){
        cylinder(r=7.917/2, h=16, $fn=64);
        cylinder(r=6.8/2, h=16.1, $fn=64);
    }
}

module bolt(length=bin_width+panel_thickness*2+12, shft=6.3/2, hd=12.8/2, thk=panel_thickness){
    //echo("bolt has length =",length);
    cylinder(r=shft, h=length, $fn=22);
    cylinder(r=hd, h=6, $fn=6);
    translate([0,0,length-5.9])
        cylinder(r=hd, h=6, $fn=6, center=false);
}

module bearing_block(w=bin_width, ht=bearing_block_thk, p=panel_thickness){
    l1 = w - p;
    difference(){
        translate([0,0,ht/2]){
            cube([l1-p/2,w,ht], center=true);
        }
        brass();
        rotate([90,0,0]){
            for (i=[1,-1]){
                translate([(l1/2 - 10) *i, ht/2, -(w+p*2+12)/2]){
                    #bolt();
                    echo("bearing block bolts coords are ",(l1/2 - 10) *i, ht/2, -(w+p*2+12)/2);
                }
            }
        for (i=[-120,82]){
            rotate([90,i,0]) translate([18,-18,-10.7])
                #limit_switch();
            }
        }
    }
}
    
module roller(wdth=62, bearing_d=22.3, bearing_h=8, shaft_d=8.6, showshaft=0){
    rad = bearing_d/2;
    ht = wdth/4;
    skinny = rad + 2;
    fat = skinny + 0.6;
    //echo("roller radius fat=", fat, "  skinny=",skinny);
    rotate([90,0,0])
        for (i=[0,1]){
            mirror([0, 0, i])
                difference(){
                    union(){
                        #cylinder(r=shaft_d/2, h=showshaft*(wdth/2+panel_thickness*2));
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

module cardstack(quant=1200){
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

module m3(length=19, head_height=3.4, nut_top=9.7, nut_thk=2.6){
    cylinder(r=3.4/2, h=length, $fn=10, center=true);
    translate([0,0,length/2 - head_height])
        cylinder(r=5.9/2, h=head_height, $fn=24);
    translate([0,0,length/2 - head_height - nut_top - nut_thk])
        cylinder(r=6.7/2, h=nut_thk, $fn=6);
}
    

module motor_mount(bin_w=bin_width, motor_w=motor_face, mount_travel=6){
    side_gap=(bin_w-motor_w)/2;
    long = bin_w + mount_travel;
    difference(){
        union(){
            cube([long, bin_w, 3], center=true);
            for (i=[1,-1]){
                 translate([0,i*(bin_w/2-side_gap/2), 4.5])
                    cube([long, side_gap, 9], center=true);
            }
        }
        for (i=[1,0,-1], j=[1,-1]){
            translate([i*(bin_w/2 - 2), j*(bin_w/2+5.3), 5.1]) rotate([90*j,0,0])
                #m3();
            echo("motor mounts from center at: ", i*(bin_w/2 - 2), j*(bin_w/2+5.3));
        }
        rotate([0,0,90])
        motor(nema=23, h=6, slide=mount_travel);
    }
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
            }
}