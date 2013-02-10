#!/usr/bin/env python
###############################################################################
#                                                                             #
#    cluster.py                                                               #
#                                                                             #
#    A collection of classes / methods used when clustering contigs           #
#                                                                             #
#    Copyright (C) Michael Imelfort                                           #
#                                                                             #
###############################################################################
#                                                                             #
#          .d8888b.                                    888b     d888          #
#         d88P  Y88b                                   8888b   d8888          #
#         888    888                                   88888b.d88888          #
#         888        888d888 .d88b.   .d88b.  88888b.  888Y88888P888          #
#         888  88888 888P"  d88""88b d88""88b 888 "88b 888 Y888P 888          #
#         888    888 888    888  888 888  888 888  888 888  Y8P  888          #
#         Y88b  d88P 888    Y88..88P Y88..88P 888 d88P 888   "   888          #
#          "Y8888P88 888     "Y88P"   "Y88P"  88888P"  888       888          #
#                                             888                             #
#                                             888                             #
#                                             888                             #
#                                                                             #
###############################################################################
#                                                                             #
#    This program is free software: you can redistribute it and/or modify     #
#    it under the terms of the GNU General Public License as published by     #
#    the Free Software Foundation, either version 3 of the License, or        #
#    (at your option) any later version.                                      #
#                                                                             #
#    This program is distributed in the hope that it will be useful,          #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of           #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
#    GNU General Public License for more details.                             #
#                                                                             #
#    You should have received a copy of the GNU General Public License        #
#    along with this program. If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

__author__ = "Michael Imelfort"
__copyright__ = "Copyright 2012"
__credits__ = ["Michael Imelfort"]
__license__ = "GPL3"
__version__ = "0.2.1"
__maintainer__ = "Michael Imelfort"
__email__ = "mike@mikeimelfort.com"
__status__ = "Alpha"

###############################################################################

from sys import exc_info, exit, stdout

from colorsys import hsv_to_rgb as htr
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import axes3d, Axes3D
from pylab import plot,subplot,axis,stem,show,figure

from numpy import unravel_index as np_unravel_index, seterr as np_seterr, abs as np_abs, append as np_append, argmax as np_argmax, argsort as np_argsort, around as np_around, array as np_array, fill_diagonal as np_fill_diagonal, finfo as np_finfo, log10 as np_log10, max as np_max, min as np_min, newaxis as np_newaxis, reshape as np_reshape, seterr as np_seterr, shape as np_shape, size as np_size, square as np_square, std as np_std, sum as np_sum, tile as np_tile, where as np_where, zeros as np_zeros
import scipy.ndimage as ndi
from scipy.spatial.distance import cdist
from scipy.cluster.vq import kmeans,vq

# GroopM imports
from profileManager import ProfileManager
from binManager import BinManager
import groopmTimekeeper as gtime

np_seterr(all='raise')      

###############################################################################
###############################################################################
###############################################################################
###############################################################################

class ClusterEngine:
    """Top level interface for clustering contigs"""
    def __init__(self, dbFileName, plot=False, force=False, numImgMaps=1, minSize=5, minVol=1000000):
        # worker classes
        self.PM = ProfileManager(dbFileName) # store our data
        self.BM = BinManager(pm=self.PM, minSize=minSize, minVol=minVol)
    
        # heat maps
        self.numImgMaps = numImgMaps
        self.imageMaps = np_zeros((self.numImgMaps,self.PM.scaleFactor,self.PM.scaleFactor))
        self.blurredMaps = np_zeros((self.numImgMaps,self.PM.scaleFactor,self.PM.scaleFactor))
        
        # we need a way to reference from the imageMaps back onto the transformed data
        self.im2RowIndicies = {}  
        
        # When blurring the raw image maps I chose a radius to suit my data, you can vary this as you like
        self.blurRadius = 2
        self.span = 30                  # amount we can travel about when determining "hot spots"
        
        # misc
        self.forceWriting = force
        self.debugPlots = plot
        self.imageCounter = 1           # when we print many images
        self.roundNumber = 0            # how many times have we tried to make a bin?

    def promptOnOverwrite(self, minimal=False):
        """Check that the user is ok with possibly overwriting the DB"""
        if(self.PM.isClustered()):
            if(not self.forceWriting):
                input_not_ok = True
                valid_responses = ['Y','N']
                vrs = ",".join([str.lower(str(x)) for x in valid_responses])
                while(input_not_ok):
                    if(minimal):
                        option = raw_input(" Overwrite? ("+vrs+") : ")
                    else: 
                        option = raw_input(" ****WARNING**** Database: '"+self.PM.dbFileName+"' has already been clustered.\n" \
                                           " If you continue you *MAY* overwrite existing bins!\n" \
                                           " Overwrite? ("+vrs+") : ")
                    if(option.upper() in valid_responses):
                        print "****************************************************************"
                        if(option.upper() == "N"):
                            print "Operation cancelled"
                            return False
                        else:
                            break
                    else:
                        print "Error, unrecognised choice '"+option.upper()+"'"
                        minimal = True
            print "Overwriting database",self.PM.dbFileName
            self.PM.dataManager.nukeBins(self.PM.dbFileName)
        return True
    
#------------------------------------------------------------------------------
# CORE CONSTRUCTION AND MANAGEMENT
        
    def makeCores(self, coreCut):
        """Cluster the contigs to make bin cores"""
        # check that the user is OK with nuking stuff...
        if(not self.promptOnOverwrite()):
            return False

        # get some data
        timer = gtime.TimeKeeper()
        self.PM.loadData(condition="length >= "+str(coreCut))
        print "    %s" % timer.getTimeStamp()
        
        # transform the data
        print "Apply data transformations"
        self.PM.transformCP()
        # plot the transformed space (if we've been asked to...)
        if(self.debugPlots):
            self.PM.renderTransCPData()
        print "    %s" % timer.getTimeStamp()
        
        # cluster and bin!
        print "Create cores"
        cum_contigs_used_good = self.initialiseCores()
        print "    %s" % timer.getTimeStamp()

        # condense cores
        print "Refine cores [begin: %d]" % len(self.BM.bins)
        #self.BM.plotBins(FNPrefix="BEFORE_OB")
        self.BM.autoRefineBins(iterate=True)
        
        num_binned = len(self.PM.binnedRowIndicies.keys())
        perc = "%.2f" % round((float(num_binned)/float(self.PM.numContigs))*100,2)
        print "   ",num_binned,"contigs across",len(self.BM.bins.keys()),"cores (",perc,"% )"
        print "    %s" % timer.getTimeStamp()

        # Now save all the stuff to disk!
        print "Saving bins"
        self.BM.saveBins()
        print "    %s" % timer.getTimeStamp()

    def initialiseCores(self):
        """Process contigs and form CORE bins"""
        num_below_cutoff = 0            # how many consecutive attempts have produced small bins
        breakout_point = 100            # how many will we allow before we stop this loop
        
        # First we need to find the centers of each blob.
        # We can make a heat map and look for hot spots
        self.populateImageMaps()
        sub_counter = 0
        print "     .... .... .... .... .... .... .... .... .... ...."
        print "%4d" % sub_counter,
        new_line_counter = 0
        num_bins = 0
        ss=0
        while(num_below_cutoff < breakout_point):
            #if(num_bins > 70):
            #    break
            stdout.flush()
            # apply a gaussian blur to each image map to make hot spots
            # stand out more from the background 
            self.blurMaps()
    
            # now search for the "hottest" spots on the blurred map
            # and check for possible bin centroids
            ss += 200
            putative_clusters = self.findNewClusterCenters(ss=ss)
            if(putative_clusters is None):
                break
            else:
                bids_made = []
                partitions = putative_clusters[0]
                [max_blur_value, max_x, max_y] = putative_clusters[1]
                self.roundNumber += 1
                sub_round_number = 1
                for center_row_indices in partitions:
                    # some of these row indices may have been eaten in a call to 
                    # bin.recruit. We need to fix this now!
                    tmp_cri = []
                    total_BP = 0
                    bin_size = 0
                    for ri in center_row_indices:
                        if ri not in self.PM.binnedRowIndicies and ri not in self.PM.restrictedRowIndicies:
                            tmp_cri.append(ri)
                            total_BP += self.PM.contigLengths[ri]
                            bin_size += 1
                    
                    center_row_indices = np_array(tmp_cri)
                    #MM__print "Round: %d tBP: %d tC: %d" % (sub_round_number, total_BP, bin_size)
                    if self.BM.isGoodBin(total_BP, bin_size):   # Can we trust very small bins?.
                        # time to make a bin
                        bin = self.BM.makeNewBin(rowIndices=center_row_indices)
                        #MM__print "NEW:", total_BP, len(center_row_indices)
                        # work out the distribution in points in this bin
                        bin.makeBinDist(self.PM.transformedCP, self.PM.averageCoverages, self.PM.kmerVals, self.PM.contigLengths)     

                        # Plot?
                        if(self.debugPlots):          
                            bin.plotBin(self.PM.transformedCP, self.PM.contigColours, self.PM.kmerVals, fileName="Image_"+str(self.imageCounter))
                            self.imageCounter += 1

                        # recruit more contigs
                        bin_size = bin.recruit(self.PM.transformedCP,
                                               self.PM.averageCoverages,
                                               self.PM.kmerVals,
                                               self.PM.contigLengths, 
                                               self.im2RowIndicies, 
                                               self.PM.binnedRowIndicies, 
                                               self.PM.restrictedRowIndicies
                                               )

                        if(self.debugPlots):
                            self.plotHeat("HM_%d.%d.png" % (self.roundNumber, sub_round_number), max=max_blur_value, x=max_x, y=max_y)
                            sub_round_number += 1

                        if(self.BM.isGoodBin(self, bin.totalBP, bin_size)):
                            # Plot?
                            bids_made.append(bin.id)
                            num_bins += 1
                            if(self.debugPlots):          
                                bin.plotBin(self.PM.transformedCP, self.PM.contigColours, self.PM.kmerVals, fileName="P_BIN_%d"%(bin.id))

                            # append this bins list of mapped rowIndices to the main list
                            self.updatePostBin(bin)
                            num_below_cutoff = 0
                            new_line_counter += 1
                            print "% 4d"%bin_size,
                        else:
                            # we just throw these indices away for now
                            self.restrictRowIndicies(bin.rowIndices)
                            self.BM.deleteBins([bin.id], force=True)
                            new_line_counter += 1
                            num_below_cutoff += 1
                            print str(bin_size).rjust(4,'X'),
        
                    else:
                        # this partition was too small, restrict these guys we don't run across them again
                        self.restrictRowIndicies(center_row_indices)
                        num_below_cutoff += 1
                        #new_line_counter += 1
                        #print center_row_indices
                        #print str(bin_size).rjust(4,'Y'),

                    # make the printing prettier
                    if(new_line_counter > 9):
                        new_line_counter = 0
                        sub_counter += 10
                        print "\n%4d" % sub_counter,
                
                # did we do anything?
                num_bids_made = len(bids_made)
                if(num_bids_made == 0):
                    # nuke the lot!
                    for row_indices in partitions:
                        self.restrictRowIndicies(row_indices)

        print "\n     .... .... .... .... .... .... .... .... .... ...."
        
        # now we need to update the PM's binIds
        bids = self.BM.getBids()
        for bid in bids:
            for row_index in self.BM.bins[bid].rowIndices:
                self.PM.binIds[row_index] = bid 

    def findNewClusterCenters(self, ss=0):
        """Find a putative cluster"""
        
        inRange = lambda x,l,u : x >= l and x < u

        # we work from the top view as this has the base clustering
        max_index = np_argmax(self.blurredMaps[0])
        max_value = self.blurredMaps[0].ravel()[max_index]

        max_x = int(max_index/self.PM.scaleFactor)
        max_y = max_index - self.PM.scaleFactor*max_x
        max_z = -1

        ret_values = [max_value, max_x, max_y]

        start_span = int(1.5 * self.span)
        span_len = 2*start_span+1
        
        if(self.debugPlots):
            self.plotRegion(max_x,max_y,max_z, fileName="Image_"+str(self.imageCounter), tag="column", column=True)
            self.imageCounter += 1

        # make a 3d grid to hold the values
        working_block = np_zeros((span_len, span_len, self.PM.scaleFactor))
        
        # go through the entire column
        (x_lower, x_upper) = self.makeCoordRanges(max_x, start_span)
        (y_lower, y_upper) = self.makeCoordRanges(max_y, start_span)
        super_putative_row_indices = []
        for p in self.im2RowIndicies:
            if inRange(p[0],x_lower,x_upper) and inRange(p[1],y_lower,y_upper):
                for row_index in self.im2RowIndicies[p]: 
                    # check that the point is real and that it has not yet been binned
                    if row_index not in self.PM.binnedRowIndicies and row_index not in self.PM.restrictedRowIndicies:
                        # this is an unassigned point. 
                        multiplier = np_log10(self.PM.contigLengths[row_index])
                        self.incrementAboutPoint3D(working_block, p[0]-x_lower, p[1]-y_lower, p[2],multiplier=multiplier)
                        super_putative_row_indices.append(row_index)
    
        # blur and find the highest value
        bwb = ndi.gaussian_filter(working_block, 8)#self.blurRadius)
        densest_index = np_unravel_index(np_argmax(bwb), (np_shape(bwb)))
        max_x = densest_index[0] + x_lower
        max_y = densest_index[1] + y_lower
        max_z = densest_index[2]

                    
        # now get the basic color of this dense point
        putative_center_row_indices = []

        (x_lower, x_upper) = self.makeCoordRanges(max_x, self.span)
        (y_lower, y_upper) = self.makeCoordRanges(max_y, self.span)
        (z_lower, z_upper) = self.makeCoordRanges(max_z, 2*self.span)

        for row_index in super_putative_row_indices:
            p = np_around(self.PM.transformedCP[row_index])
            if inRange(p[0],x_lower,x_upper) and inRange(p[1],y_lower,y_upper) and inRange(p[2],z_lower,z_upper):  
                # we are within the range!
                putative_center_row_indices.append(row_index)
         
        # make sure we have something to go on here
        if(np_size(putative_center_row_indices) == 0):
            # it's all over!
            return None
        
        if(np_size(putative_center_row_indices) == 1):
            # get out of here but keep trying
            # the calling function may restrict these indices
            return [[np_array(putative_center_row_indices)], ret_values]
        else:
            total_BP = sum([self.PM.contigLengths[i] for i in putative_center_row_indices])
            if not self.BM.isGoodBin(total_BP, len(putative_center_row_indices), ms=5):   # Can we trust very small bins?.
                # get out of here but keep trying
                # the calling function should restrict these indices
                return [[np_array(putative_center_row_indices)], ret_values]
            else:
                # we've got a few good guys here, partition them up!
                # shift these guys around a bit
                center_k_vals = np_array([self.PM.kmerVals[i] for i in putative_center_row_indices])
                k_partitions = self.partitionVals(center_k_vals)

                if(len(k_partitions) == 0):
                    return None
                else:
                    center_c_vals = np_array([self.PM.transformedCP[i][-1] for i in putative_center_row_indices])
                    #center_c_vals = np_array([self.PM.averageCoverages[i] for i in putative_center_row_indices])
                    center_c_vals -= np_min(center_c_vals)
                    c_max = np_max(center_c_vals)
                    if c_max != 0:
                        center_c_vals /= c_max
                    c_partitions = self.partitionVals(center_c_vals)

                    # take the intersection of the two partitions 
                    tmp_partition_hash_1 = {}
                    id = 1
                    for p in k_partitions:
                        for i in p:
                            tmp_partition_hash_1[i] = id
                        id += 1

                    tmp_partition_hash_2 = {}
                    id = 1
                    for p in c_partitions:
                        for i in p:
                            try:
                                tmp_partition_hash_2[(tmp_partition_hash_1[i],id)].append(i)
                            except KeyError:
                                tmp_partition_hash_2[(tmp_partition_hash_1[i],id)] = [i]
                        id += 1

                    partitions = [np_array([putative_center_row_indices[i] for i in tmp_partition_hash_2[key]]) for key in tmp_partition_hash_2.keys()]
                    return [partitions, ret_values]
            
    def expandSelection(self, startIndex, vals, stdevCutoff=0.05, maxSpread=0.1):
        """Expand a selection left and right from a staring index in a list of values
        
        Keep expanding unless the stdev of the values goes above the cutoff
        Return a list of indices into the original list
        """
        ret_list = [startIndex]   # this is what we will give back
        start_val = vals[startIndex]
        value_store = [start_val]
        
        sorted_indices = np_argsort(vals)
        max_index = len(vals)
        
        # set the upper and lower to point to the position
        # where the start resides 
        lower_index = 0
        upper_index = 0
        for i in range(max_index):
            if(sorted_indices[i] == startIndex):
                break
            lower_index += 1
            upper_index += 1
        do_lower = True
        do_upper = True
        max_index -= 1
        
        while(do_lower or do_upper):
            if(do_lower):
                do_lower = False
                if(lower_index > 0):
                    try_val = vals[sorted_indices[lower_index - 1]]
                    if(np_abs(try_val - start_val) < maxSpread):
                        try_array = value_store + [try_val]
                        if(np_std(try_array) < stdevCutoff):
                            value_store = try_array
                            lower_index -= 1
                            ret_list.append(sorted_indices[lower_index])
                            do_lower = True
            if(do_upper):
                do_upper = False
                if(upper_index < max_index):
                    try_val = vals[sorted_indices[upper_index + 1]]
                    if(np_abs(try_val - start_val) < maxSpread):
                        try_array = value_store + [try_val]
                        if(np_std(try_array) < stdevCutoff):
                            value_store = try_array
                            upper_index += 1
                            ret_list.append(sorted_indices[upper_index])
                            do_upper = True
        return sorted(ret_list)

    def partitionVals(self, vals, stdevCutoff=0.04, maxSpread=0.15):
        """Work out where shifts in kmer/coverage vals happen"""
        partitions = []
        working_list = list(vals)
        fix_dict = dict(zip(range(len(working_list)),range(len(working_list))))
        while(len(working_list) > 2):
            cf = CenterFinder()
            c_index = cf.findArrayCenter(working_list)
            expanded_indices = self.expandSelection(c_index, working_list, stdevCutoff=stdevCutoff, maxSpread=maxSpread)
            # fix any munges from previous deletes
            morphed_indices = [fix_dict[i] for i in expanded_indices]
            partitions.append(morphed_indices)
            # shunt the indices to remove down!
            shunted_indices = []
            for offset, index in enumerate(expanded_indices):
                shunted_indices.append(index - offset)

            #print "FD:", fix_dict 
            #print "EI:", expanded_indices
            #print "MI:", morphed_indices
            #print "SI:", shunted_indices
            
            # make an updated working list and fix the fix dict
            nwl = []
            nfd = {}
            shifter = 0
            for i in range(len(working_list) - len(shunted_indices)):
                #print "================="
                if(len(shunted_indices) > 0):
                    #print i, shunted_indices[0], shifter
                    if(i >= shunted_indices[0]):
                        tmp = shunted_indices.pop(0)
                        shifter += 1
                        # consume any and all conseqs
                        while(len(shunted_indices) > 0):
                            if(shunted_indices[0] == tmp):
                                shunted_indices.pop(0)
                                shifter += 1
                            else:
                                break
                #else:
                #    print i, "_", shifter

                nfd[i] = fix_dict[i + shifter]
                nwl.append(working_list[i + shifter])

                #print nfd
                #print nwl
                
            fix_dict = nfd
            working_list = nwl
            
        if(len(working_list) > 0):
            partitions.append(fix_dict.values())       
        return partitions
        
#------------------------------------------------------------------------------
# DATA MAP MANAGEMENT 

    def populateImageMaps(self):
        """Load the transformed data into the main image maps"""
        # reset these guys... JIC
        self.imageMaps = np_zeros((self.numImgMaps,self.PM.scaleFactor,self.PM.scaleFactor))
        self.im2RowIndicies = {}
        
        # add to the grid wherever we find a contig
        row_index = -1
        for point in np_around(self.PM.transformedCP):
            row_index += 1
            # can only bin things once!
            if row_index not in self.PM.binnedRowIndicies and row_index not in self.PM.restrictedRowIndicies:
                # add to the row_index dict so we can relate the 
                # map back to individual points later
                p = tuple(point)
                if p in self.im2RowIndicies:
                    self.im2RowIndicies[p].append(row_index)
                else:
                    self.im2RowIndicies[p] = [row_index]
                
                # now increment in the grid
                # for each point we encounter we incrmement
                # it's position + the positions to each side
                # and touching each corner
                self.incrementViaRowIndex(row_index, p)

    def incrementViaRowIndex(self, rowIndex, point=None):
        """Wrapper to increment about point"""
        if(point is None):
            point = tuple(np_around(self.PM.transformedCP[rowIndex]))
        #px = point[0]
        #py = point[1]
        #pz = point[2]
        multiplier = np_log10(self.PM.contigLengths[rowIndex])
        self.incrementAboutPoint(0, point[0], point[1], multiplier=multiplier)
        if(self.numImgMaps > 1):
            self.incrementAboutPoint(1, self.PM.scaleFactor - point[2] - 1, point[1], multiplier=multiplier)
            self.incrementAboutPoint(2, self.PM.scaleFactor - point[2] - 1, self.PM.scaleFactor - point[0] - 1, multiplier=multiplier)

    def decrementViaRowIndex(self, rowIndex, point=None):
        """Wrapper to decrement about point"""
        if(point is None):
            point = tuple(np_around(self.PM.transformedCP[rowIndex]))
        #px = point[0]
        #py = point[1]
        #pz = point[2]
        multiplier = np_log10(self.PM.contigLengths[rowIndex])
        self.decrementAboutPoint(0, point[0], point[1], multiplier=multiplier)
        if(self.numImgMaps > 1):
            self.decrementAboutPoint(1, self.PM.scaleFactor - point[2] - 1, point[1], multiplier=multiplier)
            self.decrementAboutPoint(2, self.PM.scaleFactor - point[2] - 1, self.PM.scaleFactor - point[0] - 1, multiplier=multiplier)

    def incrementAboutPoint(self, view_index, px, py, valP=1, valS=0.6, valC=0.2, multiplier=1):
        """Increment value at a point in the 2D image maps
        
        Increment point by valP, increment neighbouring points at the
        sides and corners of the target point by valS and valC
        
        multiplier is proportional to the contigs length
        """
        valP *= multiplier
        valS *= multiplier
        valC *= multiplier
        if px > 0:
            if py > 0:
                self.imageMaps[view_index,px-1,py-1] += valC      # Top left corner
            self.imageMaps[view_index,px-1,py] += valS            # Top
            if py < self.PM.scaleFactor-1:             
                self.imageMaps[view_index,px-1,py+1] += valC      # Top right corner

        if py > 0:
            self.imageMaps[view_index,px,py-1] += valS            # Left side
        self.imageMaps[view_index,px,py] += valP                  # Point
        if py < self.PM.scaleFactor-1:             
            self.imageMaps[view_index,px,py+1] += valS            # Right side

        if px < self.PM.scaleFactor-1:
            if py > 0:
                self.imageMaps[view_index,px+1,py-1] += valC      # Bottom left corner
            self.imageMaps[view_index,px+1,py] += valS            # Bottom
            if py < self.PM.scaleFactor-1:             
                self.imageMaps[view_index,px+1,py+1] += valC      # Bottom right corner

    def decrementAboutPoint(self, view_index, px, py, valP=1, valS=0.6, valC=0.2, multiplier=1):
        """Decrement value at a point in the 2D image maps
        
        multiplier is proportional to the contigs length
        """        
        valP *= multiplier
        valS *= multiplier
        valC *= multiplier
        if px > 0:
            if py > 0:
                self.safeDecrement(self.imageMaps[view_index], px-1, py-1, valC) # Top left corner
            self.safeDecrement(self.imageMaps[view_index], px-1, py, valS)       # Top    
            if py < self.PM.scaleFactor-1:
                self.safeDecrement(self.imageMaps[view_index], px-1, py+1, valC) # Top right corner

        if py > 0:
            self.safeDecrement(self.imageMaps[view_index], px, py-1, valS)       # Left side
        self.safeDecrement(self.imageMaps[view_index], px, py, valP)             # Point
        if py < self.PM.scaleFactor-1:             
            self.safeDecrement(self.imageMaps[view_index], px, py+1, valS)       # Right side

        if px < self.PM.scaleFactor-1:
            if py > 0:
                self.safeDecrement(self.imageMaps[view_index], px+1, py-1, valC) # Bottom left corner
            self.safeDecrement(self.imageMaps[view_index], px+1, py, valS)       # Bottom    
            if py < self.PM.scaleFactor-1:             
                self.safeDecrement(self.imageMaps[view_index], px+1, py+1, valC) # Bottom right corner
                    
    def safeDecrement(self, map, px, py, value):
        """Decrement a value and make sure it's not negative or something shitty"""
        map[px][py] -= value
        if map[px][py] < np_finfo(float).eps:
            map[px][py] = 0

    def incrementAboutPoint3D(self, workingBlock, px, py, pz, vals=(6.4,4.9,2.5,1.6), multiplier=1):
        """Increment a point found in a 3D column
        
        used when finding the centroid of a hot area
        update the 26 points which surround the centre point
        z spans the height of the entire column, x and y have been offset to
        match the column subspace
        
        multiplier is proportional to the contigs length
        """
        valsM = [x*multiplier for x in vals]
        # top slice
        if pz < self.PM.scaleFactor-1:
            self.subIncrement3D(workingBlock, px, py, pz+1, valsM, 1)
        
        # center slice
        self.subIncrement3D(workingBlock, px, py, pz, valsM, 0)
        
        # bottom slice
        if pz > 0:
            self.subIncrement3D(workingBlock, px, py, pz-1, valsM, 1)
        
    def subIncrement3D(self, workingBlock, px, py, pz, vals, offset):
        """AUX: Called from incrementAboutPoint3D does but one slice
        
        multiplier is proportional to the contigs length
        """       
        # get the size of the working block
        shape = np_shape(workingBlock)
        if px > 0:
            if py > 0:
                workingBlock[px-1,py-1,pz] += vals[offset + 2]      # Top left corner
            workingBlock[px-1,py,pz] += vals[offset + 1]            # Top
            if py < shape[1]-1:             
                workingBlock[px-1,py+1,pz] += vals[offset + 2]      # Top right corner

        if py > 0:
            workingBlock[px,py-1,pz] += vals[offset + 1]            # Left side
        workingBlock[px,py,pz] += vals[offset]                      # Point
        if py < shape[1]-1:             
            workingBlock[px,py+1,pz] += vals[offset + 1]            # Right side

        if px < shape[0]-1:
            if py > 0:
                workingBlock[px+1,py-1,pz] += vals[offset + 2]      # Bottom left corner
            workingBlock[px+1,py,pz] += vals[offset + 1]            # Bottom
            if py < shape[1]-1:             
                workingBlock[px+1,py+1,pz] += vals[offset + 2]      # Bottom right corner
    
    def blurMaps(self):
        """Blur the 2D image maps"""
        self.blurredMaps = np_zeros((self.numImgMaps,self.PM.scaleFactor,self.PM.scaleFactor))
        for i in range(self.numImgMaps): # top, front and side
            self.blurredMaps[i,:,:] = ndi.gaussian_filter(self.imageMaps[i,:,:], 8)#self.blurRadius) 

    def makeCoordRanges(self, pos, span):
        """Make search ranges which won't go out of bounds"""
        lower = pos-span
        upper = pos+span+1
        if(lower < 0):
            lower = 0
        if(upper > self.PM.scaleFactor):
            upper = self.PM.scaleFactor
        return (lower, upper)
    
    def updatePostBin(self, bin):
        """Update data structures after assigning contigs to a new bin"""
        for row_index in bin.rowIndices:
            self.setRowIndexAssigned(row_index)
            
    def setRowIndexAssigned(self, rowIndex):
        """fix the data structures to indicate that rowIndex belongs to a bin
        
        Use only during initial core creation
        """        
        if(rowIndex not in self.PM.restrictedRowIndicies and rowIndex not in self.PM.binnedRowIndicies):
            self.PM.binnedRowIndicies[rowIndex] = True
            # now update the image map, decrement
            self.decrementViaRowIndex(rowIndex)

    def setRowIndexUnassigned(self, rowIndex):
        """fix the data structures to indicate that rowIndex no longer belongs to a bin
        
        Use only during initial core creation
        """
        if(rowIndex in self.PM.restrictedRowIndicies and rowIndex not in self.PM.binnedRowIndicies):
            del self.PM.binnedRowIndicies[rowIndex]
            # now update the image map, increment
            self.incrementViaRowIndex(rowIndex)

    def restrictRowIndicies(self, indices):
        """Add these indices to the restricted list"""
        for row_index in indices:
            # check that it's not binned or already restricted
            if(row_index not in self.PM.restrictedRowIndicies and row_index not in self.PM.binnedRowIndicies):
                self.PM.restrictedRowIndicies[row_index] = True
                # now update the image map, decrement
                self.decrementViaRowIndex(row_index)
    
#------------------------------------------------------------------------------
# IO and IMAGE RENDERING 

    def plotRegion(self, px, py, pz, fileName="", tag="", column=False):
        """Plot the region surrounding a point """
        import matplotlib as mpl
        disp_vals = np_array([])
        disp_cols = np_array([])
        num_points = 0
        # plot all points within span
        (z_lower, z_upper) = self.makeCoordRanges(pz, self.span)
        if(column):
            z_lower = 0
            z_upper = self.PM.scaleFactor - 1

        (x_lower, x_upper) = self.makeCoordRanges(px, self.span)
        (y_lower, y_upper) = self.makeCoordRanges(py, self.span)
        for z in range(z_lower, z_upper):
            realz = self.PM.scaleFactor - z - 1
            for x in range(x_lower, x_upper):
                for y in range(y_lower, y_upper):
                    if((x,y,realz) in self.im2RowIndicies):
                        for row_index in self.im2RowIndicies[(x,y,realz)]:
                            if row_index not in self.PM.binnedRowIndicies and row_index not in self.PM.restrictedRowIndicies:
                                num_points += 1
                                disp_vals = np_append(disp_vals, self.PM.transformedCP[row_index])
                                disp_cols = np_append(disp_cols, self.PM.contigColours[row_index])
        
        # make a black mark at the max values
        small_span = self.span/2
        (x_lower, x_upper) = self.makeCoordRanges(px, small_span)
        (y_lower, y_upper) = self.makeCoordRanges(py, small_span)
        (z_lower, z_upper) = self.makeCoordRanges(pz, small_span)
        for z in range(z_lower, z_upper):
            realz = self.PM.scaleFactor - z - 1
            for x in range(x_lower, x_upper):
                for y in range(y_lower, y_upper):
                    if((x,y,realz) in self.im2RowIndicies):
                        for row_index in self.im2RowIndicies[(x,y,realz)]:
                            if row_index not in self.PM.binnedRowIndicies and row_index not in self.PM.restrictedRowIndicies:
                                num_points += 1
                                disp_vals = np_append(disp_vals, self.PM.transformedCP[row_index])
                                disp_cols = np_append(disp_cols, htr(0,0,0))
        # reshape
        disp_vals = np_reshape(disp_vals, (num_points, 3))
        disp_cols = np_reshape(disp_cols, (num_points, 3))
        
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        cm = mpl.colors.LinearSegmentedColormap('my_colormap', disp_cols, 1024)
        result = ax.scatter(disp_vals[:,0], disp_vals[:,1], disp_vals[:,2], edgecolors=disp_cols, c=disp_cols, cmap=cm, marker='.')
        title = str.join(" ", ["Focus at: (",str(px), str(py), str(self.PM.scaleFactor - pz - 1),")\n",tag])
        plt.title(title)
      
        if(fileName != ""):
            fig.set_size_inches(6,6)
            plt.savefig(fileName,dpi=300)
        elif(show):
            plt.show()
        
        plt.close(fig)
        del fig
    
    def plotHeat(self, fileName = "", max=-1, x=-1, y=-1):
        """Print the main heat maps
        
        Useful for debugging
        """
        fig = plt.figure()
        images = []
        ax = None
        if(self.numImgMaps == 1):
            ax = fig.add_subplot(121)
            images.append(ax.imshow(self.blurredMaps[0,:,:]**0.5))
            if(max > 0):
                title = "Max value: %f (%f, %f)" % (max, x, y)
                plt.title(title)
        else:
            ax = fig.add_subplot(231)
            images.append(ax.imshow(self.blurredMaps[0,:,:]**0.5))
            if(max > 0):
                title = str.join(" ", ["Max value:",str(max)])
                plt.title(title)
            ax = fig.add_subplot(232)
            images.append(ax.imshow(self.blurredMaps[1,:,:]**0.5))
            ax = fig.add_subplot(233)
            images.append(ax.imshow(self.blurredMaps[2,:,:]**0.5))

        if(self.numImgMaps == 1):
            ax = fig.add_subplot(122)
            images.append(ax.imshow(self.imageMaps[0,:,:]**0.5))
        else:
            ax = fig.add_subplot(234)
            images.append(ax.imshow(self.imageMaps[0,:,:]**0.5))
            ax = fig.add_subplot(235)
            images.append(ax.imshow(self.imageMaps[1,:,:]**0.5))
            ax = fig.add_subplot(236)
            images.append(ax.imshow(self.imageMaps[2,:,:]**0.5))
        
        if(fileName != ""):
            if(self.numImgMaps == 1):
                fig.set_size_inches(12,6)
            else:
                fig.set_size_inches(18,18)
                
            plt.savefig(fileName,dpi=300)
        elif(show):
            plt.show()

        plt.close(fig)
        del fig

###############################################################################
###############################################################################
###############################################################################
###############################################################################

class CenterFinder:
    """When a plain old mean won't cut it

    Uses a balloon hitting algorithm. Imagine walking along a "path",
    (through the array) hitting a balloon into the air each time you
    come across a value. Gravity is bringing the balloon down. If we plot
    the height of the ball vs array index then the highest the balloon
    reaches is the index in the center of the densest part of the array 
    """
    def __init__(self): pass
    
    def findArrayCenter(self, vals):
        """Find the center of the numpy array vals, return the index of the center"""
        # parameters
        current_val_max = -1
        delta = 0
        bounce_amount = 0.1
        height = 0
        last_val= 0

        working = np_array([])
        final_index = -1
        
        # sort and normalise between 0 -> 1
        sorted_indices = np_argsort(vals)
        vals_sorted = [vals[i] for i in sorted_indices]
        vals_sorted -= vals_sorted[0]
        if(vals_sorted[-1] != 0):
            vals_sorted /= vals_sorted[-1]        

        #print vals_sorted
        
        # run through in one direction
        for val in vals_sorted:
            # calculate delta
            delta = val - last_val
            # reduce the current value according to the delta value
            height = self.reduceViaDelta(height, bounce_amount, delta)
            # bounce the ball up
            height += bounce_amount
            
            # store the height
            working = np_append(working, height)
            final_index += 1

            # save the last val            
            last_val = val

        current_val_max = -1
        height = 0
        last_val = 0
        
        #print "===W==="
        #print working
        #print "===E==="
        
        # run through in the reverse direction
        vals_sorted = vals_sorted[::-1]
        for val in vals_sorted:
            if last_val == 0:
                delta = 0
            else:
                delta = last_val - val
            height = self.reduceViaDelta(height, bounce_amount, delta)
            height += bounce_amount
            # add to the old heights
            working[final_index] += height
            final_index -= 1
            last_val = val

        #print working
        #print "==EEE=="

        # find the original index!
        return sorted_indices[np_argmax(working)]
    
    def reduceViaDelta(self, height, bounce_amount, delta):
        """Reduce the height of the 'ball'"""
        perc = (delta / bounce_amount)**0.5
        if(perc > 1):
            #print height, delta, 1, " H: ", 0
            return 0
        #print height, delta, (1-perc), " H: ", (height * (1-perc)) 
        return height * (1-perc)

###############################################################################
###############################################################################
###############################################################################
###############################################################################
