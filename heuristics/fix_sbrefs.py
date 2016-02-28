#!/usr/bin/env python
import os, sys, glob, json

sbrefs = glob.glob(sys.argv[1] + "*/*/*_sbref.json")
for sbref in sbrefs:
    if "dwi" in sbref:
        rel = sbref.replace("_sbref", "_dwi")
    else:
        rel = sbref.replace("_sbref", "_bold")
    #print rel
    #print os.path.exists(rel)
    try:
        with open(rel) as data_file:    
            rel_data = json.load(data_file)
            #print rel_data
    except:
        print "Warning: could not fidd %s"%rel
    
    with open(sbref) as data_file:    
        sbref_data = json.load(data_file)
        #print sbref_data

    for key in sbref_data.keys():
        new_value = rel_data[key]
        if key == "RepetitionTime":
            new_value *= rel_data["MultibandAccelerationFactor"]
        sbref_data[key] = new_value
        
        json.dump(sbref_data, open(sbref, "w"), sort_keys=True, indent=4, separators=(',', ': '))
    