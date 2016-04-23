incup = 53/2;
wallthk = 1.6;
cupside = incup + wallthk;
fudge = 0.55; //0.7 on first try
airgap_outside = cupside + wallthk + fudge*2;
outcup = airgap_outside + wallthk;

cupholder_in = cupside + fudge;
cupholder_wall = cupholder_in + wallthk;
cupholder_gap = cupholder_wall + wallthk + fudge*2;
cupholder_outside = cupholder_gap + wallthk;
echo("cupholder has diameter of:", cupholder_outside*2);
cup_travel = 10;
cup_extension = 25;
cup_base_ht = 20;
cup_rim_thk = 2;
cup_ht = cup_base_ht + cup_extension + cup_travel + cup_rim_thk;
outcup_ht = cup_ht - cup_travel - cup_extension;
cupholder_inside_ht = outcup_ht - fudge;
cupholder_outside_ht = cupholder_inside_ht + cup_travel + fudge;

spring_rad = 4.1;
spring_len = 30;  // compressed

cupholder_template();

module twogirls(){
scale([1, (incup*2 + 22)/(incup*2), 1]){
    cup();
translate([cupholder_outside*2, 0, 0])
    cupholder();
}

}
module rimjob(ht=1, inner=1, outer=2){
    difference(){
        cylinder(r=outer, h=ht, $fn=384);
        translate([0,0,-0.1])
            cylinder(r=inner, h=ht+0.2, $fn=384);
    }
}

module cup(){
    //base
    rimjob(ht=cup_rim_thk, inner=incup, outer=outcup);
    //inner cup
    rimjob(ht=cup_ht, inner=incup, outer=cupside);
    //outer cup
    rimjob(ht=outcup_ht, inner=airgap_outside, outer=outcup);
}

module cupholder(){
    //base
    rimjob(ht=cup_rim_thk, inner=cupholder_in, outer=cupholder_outside);
    //inner ring
    rimjob(ht=cupholder_inside_ht, inner=cupholder_in, outer=cupholder_wall);
    // outer ring
    rimjob(ht=cupholder_outside_ht, inner=cupholder_gap, outer=cupholder_outside);
}
   

module cupholder_template(){
    sfact = (incup*2 + 22)/(incup*2);
    center_to_rim = sfact * (airgap_outside - 0.9);
    difference(){
        union(){
            scale([1, sfact, 1]){
                echo("scale factor is:", sfact, "mm to center rim:", center_to_rim);
                rimjob(ht=cup_rim_thk, inner=incup, outer=cupholder_outside+wallthk);
                #rimjob(ht=cup_rim_thk+.1, inner=cupholder_gap, outer=cupholder_outside);
                }
             for (i=[1,-1]){
                translate([0,i*center_to_rim,0])
                    scale([1.5, 1, 1])
                        cylinder(r=spring_rad + 1, h=spring_len+1.7, $fn=64);
             }
         }
         for (i=[1,-1]){
             // spring holes
            translate([0,i*(center_to_rim),-0.1])
                    cylinder(r=spring_rad, h=spring_len+0.1, $fn=64);
             // door hinge holes
            translate([5*i,-50, 8])
                rotate([-90,0,0])
                    #cylinder(r=0.9, h=100, $fn=6);
         }

    }
}

