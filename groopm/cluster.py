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
__version__ = "0.0.1"
__maintainer__ = "Michael Imelfort"
__email__ = "mike@mikeimelfort.com"
__status__ = "Development"

###############################################################################
import sys
import math
import colorsys
import random

import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import axes3d, Axes3D
from pylab import plot,subplot,axis,stem,show,figure

import numpy as np
import scipy.ndimage as ndi
import scipy.spatial.distance as ssdist
from scipy.stats import kstest

# GroopM imports
import PCA
import mstore

###############################################################################
###############################################################################
###############################################################################
###############################################################################
class DataBlob:
    """Interacts with the groopm datamanager and local data fields
    
    Simple a wrapper around a group of numpy arrays
    """
    def __init__(self, dbFileName, maxRows=0, force=False):
        # data
        self.dataManager = mstore.GMDataManager()       # most data is saved to hdf
        self.covProfiles = np.array([])
        self.contigNames = np.array([])
        self.contigLengths = np.array([])
        self.auxProfiles = np.array([]) 
        self.auxColors = np.array([])
        self.kmerSigs = np.array([])
        self.bins = np.array([])
        self.transformedData = np.array([])             # the munged data points
        
        # misc
        self.dbFileName = dbFileName        # db containing all the data we'd like to use
        self.forceWriting = force           # overwrite existng values silently?
        self.maxRows = maxRows              # limit the number of rows we'll parse

    def loadData(self, condition=""):
        """Load pre-parsed data"""
        try:
            indicies = self.dataManager.getConditionalIndicies(self.dbFileName, condition=condition)
            self.covProfiles = self.dataManager.getCoverageProfiles(self.dbFileName, indicies=indicies)
            self.auxProfiles = self.dataManager.getAuxProfiles(self.dbFileName, indicies=indicies)
            self.bins = self.dataManager.getBins(self.dbFileName, indicies=indicies)
            self.contigNames = self.dataManager.getContigNames(self.dbFileName, indicies=indicies)
            self.contigLengths = self.dataManager.getContigLengths(self.dbFileName, indicies=indicies)
            self.kmerSigs = self.dataManager.getKmerSigs(self.dbFileName, indicies=indicies)
        except:
            print "Error loading DB:", self.dbFileName, sys.exc_info()[0]
            raise
        
###############################################################################
###############################################################################
###############################################################################
###############################################################################
class ClusterEngine:
    """Top level interface for clustering contigs"""
    def __init__(self, dbFileName, plot=False, outFile="", maxRows=0, force=False):
        # Data
        self.dataBlob = DataBlob(dbFileName)
        
        # associated classes
        self.dataTransformer = DataTransformer(self.dataBlob)
        self.clusterBlob = ClusterBlob(self.dataBlob)
    
        # misc
        self.plot = plot
        self.outFile = outfile
        self.force = force
        
    def cluster(self):
        """Cluster the contigs"""
        # check that the user is OK with nuking stuff...
        if(not self.forceWriting):
            if(self.dataManager.isClustered(self.dbFileName)):
                option = raw_input(" ****WARNING**** Database: '"+self.dbFileName+"' has already been clustered.\n" \
                                   " If you continue you *MAY* overwrite existing bins!\n" \
                                   " Overwrite? (y,n) : ")
                print "****************************************************************"
                if(option.upper() != "Y"):
                    print "Operation cancelled"
                    return False
                else:
                    print "Overwriting database",self.dbFileName

        # get some data
        self.dataBlob.loadData()
    
        # transform the data
        self.dataTransformer.transformData(kf, sf)
    
        # cluster and bin!
        self.clusterBlob.clusterPoints()

        return
    
        # cluster points
        #if("" != options.secondary_data):
        #    dt.clusterPoints()
        #    dt.renderTransData("postclust.png")
        
        # write to the output file
#        if("" != self.outputFile):
#            dt.writeOutput(self.outputFile, dialect)
    
        # plot the transformed space (if we've been asked to...)
        if(self.doPlots):
            self.dataTransformer.renderTransData()

        # all good!
        return True

###############################################################################
###############################################################################
###############################################################################
###############################################################################
class DataTransformer:
    """Munge raw profile data into a 3D coord system
    
    Loads data from a h5 database. This DB should have been built
    using groopm parse
    """
    def __init__( self, db, maxRows = 0, scaleFactor=1000):
        
        # data 
        self.dataBlob = db

        # more about data storage
        self.covProfileRows = 0
        self.covProfileCols = 0
        self.auxRows = 0
        
        # constraints
        self.maxRows = maxRows                   # limit the number of rows we'll parse
        
        # transformed data strorage
        self.radialVals = np.array([])           # for storing the distance from the origin to each 
        self.scaleFactor = scaleFactor           # scale every thing in the transformed data to this dimension
        
#------------------------------------------------------------------------------
# DATA TRANSFORMATIONS 

    def transformData(self, kf=10, sf=1):
        """Perform all the necessary data transformations"""
        print "Applying transformations..."
        # Update this guy now we know how big he has to be
        # do it this way because we may apply successive transforms to this
        # guy and this is a neat way of clearing the data 
        s = (self.covProfileRows,3)
        self.transformedData = np.zeros(s)
        tmp_data = np.array([])
        
        # the radius of the mapping sphere
        RX = np.amax(self.covProfiles)
        RD = np.median(self.covProfiles)
        
        # first we shift the edge values accordingly and then 
        # map each point onto the surface of a hyper-sphere
        print "Start radial mapping..."
        for point in self.covProfiles:
            norm = np.linalg.norm(point)
            self.radialVals = np.append(self.radialVals, norm)
            tmp_data = np.append(tmp_data, self.rotateVectorAndScale(point, RX, RD, phi_max=15))

        # reshape this guy
        tmp_data = np.reshape(tmp_data, (self.covProfileRows,self.covProfileCols))
    
        # now we use PCA to map the surface points back onto a 
        # 2 dimensional plane, thus making the data usefuller
        index = 0
        if(self.covProfileCols == 2):
            print "Skipping dimensionality reduction"
            for point in self.covProfiles:
                self.transformedData[index,0] = tmp_data[index,0]
                self.transformedData[index,1] = tmp_data[index,1]
                self.transformedData[index,2] = math.log(self.radialVals[index])
                index += 1
        else:    
            # Project the points onto a 2d plane which is orthonormal
            # to the Z axis
            print "Start dimensionality reduction..."
            PCA.Center(tmp_data,verbose=0)
            p = PCA.PCA(tmp_data)
            components = p.pc()
            for point in components:
                self.transformedData[index,0] = components[index,0]
                self.transformedData[index,1] = components[index,1]
                self.transformedData[index,2] = math.sqrt(math.log(self.radialVals[index]))
                index += 1

        # finally scale the matrix to make it equal in all dimensions                
        min = np.amin(self.transformedData, axis=0)
        max = np.amax(self.transformedData, axis=0)
        max = max - min
        max = max / (self.scaleFactor-1)
        for i in range(0,3):
            self.transformedData[:,i] = (self.transformedData[:,i] -  min[i])/max[i]

    def rotateVectorAndScale(self, point, RX, RD, phi_max=15, las=0):
        """
        Move a vector closer to the center of the positive quadrant
        
        Find the co-ordinates of its projection
        onto the surface of a hypersphere with radius R
        
        What?...  ...First some definitions:
       
        For starters, think in 3 dimensions, then take it out to N.
        Imagine all points (x,y,z) on the surface of a sphere
        such that all of x,y,z > 0. ie trapped within the positive
        quadrant.
       
        Consider the line x = y = z which passes through the origin
        and the point on the surface at the "center" of this quadrant.
        Call this line the "main mapping axis". Let the unit vector 
        coincident with this line be called A.
       
        Now think of any other vector V also located in the positive
        quadrant. The goal of this function is to move this vector
        closer to the MMA. Specifically, if we think about the plane
        which contains both V and A, we'd like to rotate V within this
        plane about the origin through phi degrees in the direction of
        A.
        
        Once this has been done, we'd like to project the rotated co-ords 
        onto the surface of a hypersphere with radius R. This is a simple
        scaling operation.
       
        We calculate phi based on theta. The idea is that vectors closer
        to the corners should be pertubed more than those closer to the center.
        set phi max as the divisor in a radial fraction.
        
        Ie set to '12' for pi/12 = 15 deg; 6 = pi/6 = 30 deg etc
        """
        # the vector we wish to move closer too...
        center_vector = np.ones_like(point)

        # unitise
        center_vector /= np.linalg.norm(center_vector)
        
        # we need the angle between this vector and one of the axes
        ax = np.zeros_like(point)
        ax[0] = 1
        
        if(0 == las):
            las = np.arccos(np.dot(ax,center_vector)/np.linalg.norm(ax)/np.linalg.norm(center_vector))
        
        # find the existing angle between them theta
        theta = self.getAngBetween(point, center_vector)
        
        # at the boundary (theta = pi/4) we want max rotation
        # at the center we like 0 rotation. For simplicity, let's use the logistic function!
        lim = np.pi
        phi = (np.pi/phi_max) / (1 + np.exp(-(2*lim)/las*theta + lim))                 # logistic function  
        
        # now we can find a vector which approximates the rotation of unit(V)
        # by phi. It's norm will be a bit wonky but we're going to scale it anywho...
        V_p = ((point / np.linalg.norm(point)) * ( theta - phi ) + center_vector * phi ) / theta
        
        # finally scale V_p and return
        point_r = np.linalg.norm(point)
        #scale_r = (RN - point_r)/(RX - RN) + 2                              # linear
        K = RD/2
        scale_r = (((RD - K) * (np.log(point_r))) / np.log(RX)) + K    # log
        return scale_r * (V_p / np.linalg.norm(V_p))
        
    def getAngBetween(self, P1, P2):
        """Return the angle between two points"""
        # find the existing angle between them theta
        c = np.dot(P1,P2)/np.linalg.norm(P1)/np.linalg.norm(P2) 
        # rounding errors hurt everyone...
        if(c > 1):
            c = 1
        elif(c < -1):
            c = -1
        return np.arccos(c) # in radians

#------------------------------------------------------------------------------
# IO and IMAGE RENDERING 
    
    def writeOutput(self, CSVFileName, dialect):
        """Write transformed data to file"""
        outCSV = csv.writer(open(CSVFileName, 'wb'), dialect)
        outCSV.writerow(["'name'","'x'","'y'","'z'"])
        for index in range (0,self.covProfileRows):
            outCSV.writerow([self.contigNames[index], self.transformedData[index,0], self.transformedData[index,1], self.transformedData[index,2]])

    def plotTransViews(self, tag="fordens"):
        """Plot top, side and front views of the transformed data"""
        self.renderTransData(tag+"_top.png",azim = 0, elev = 90)
        self.renderTransData(tag+"_front.png",azim = 0, elev = 0)
        self.renderTransData(tag+"_side.png",azim = 90, elev = 0)

    def renderTransData(self, fileName="", show=True, elev=45, azim=45, all=False):
        """Plot transformed data in 3D"""
        fig = plt.figure()
        if(self.auxondaryFileName != ""):
            if(all):
                myAXINFO = {
                    'x': {'i': 0, 'tickdir': 1, 'juggled': (1, 0, 2),
                    'color': (0, 0, 0, 0, 0)},
                    'y': {'i': 1, 'tickdir': 0, 'juggled': (0, 1, 2),
                    'color': (0, 0, 0, 0, 0)},
                    'z': {'i': 2, 'tickdir': 0, 'juggled': (0, 2, 1),
                    'color': (0, 0, 0, 0, 0)},
                }

                ax = fig.add_subplot(131, projection='3d')
                ax.scatter(self.transformedData[:,0], self.transformedData[:,1], self.transformedData[:,2], edgecolors=self.auxColors, c=self.auxColors, marker='.')
                ax.azim = 0
                ax.elev = 0
                for axis in ax.w_xaxis, ax.w_yaxis, ax.w_zaxis:
                    for elt in axis.get_ticklines() + axis.get_ticklabels():
                        elt.set_visible(False)
                ax.w_xaxis._AXINFO = myAXINFO
                ax.w_yaxis._AXINFO = myAXINFO
                ax.w_zaxis._AXINFO = myAXINFO
                
                ax = fig.add_subplot(132, projection='3d')
                ax.scatter(self.transformedData[:,0], self.transformedData[:,1], self.transformedData[:,2], edgecolors=self.auxColors, c=self.auxColors, marker='.')
                ax.azim = 90
                ax.elev = 0
                for axis in ax.w_xaxis, ax.w_yaxis, ax.w_zaxis:
                    for elt in axis.get_ticklines() + axis.get_ticklabels():
                        elt.set_visible(False)
                ax.w_xaxis._AXINFO = myAXINFO
                ax.w_yaxis._AXINFO = myAXINFO
                ax.w_zaxis._AXINFO = myAXINFO
                
                ax = fig.add_subplot(133, projection='3d')
                ax.scatter(self.transformedData[:,0], self.transformedData[:,1], self.transformedData[:,2], edgecolors=self.auxColors, c=self.auxColors, marker='.')
                ax.azim = 0
                ax.elev = 90
                for axis in ax.w_xaxis, ax.w_yaxis, ax.w_zaxis:
                    for elt in axis.get_ticklines() + axis.get_ticklabels():
                        elt.set_visible(False)
                ax.w_xaxis._AXINFO = myAXINFO
                ax.w_yaxis._AXINFO = myAXINFO
                ax.w_zaxis._AXINFO = myAXINFO
            else:
                ax = fig.add_subplot(111, projection='3d')
                ax.scatter(self.transformedData[:,0], self.transformedData[:,1], self.transformedData[:,2], edgecolors=self.auxColors, c=self.auxColors, marker='.')
                ax.azim = azim
                ax.elev = elev
                ax.set_axis_off()

                #ax = fig.add_subplot(122, projection='3d')
                #ax.scatter(self.covProfiles[:,0], self.covProfiles[:,1], self.covProfiles[:,2], edgecolors=self.auxColors, c=self.auxColors, marker='.')
                #ax.azim = azim
                #ax.elev = elev
                #ax.set_axis_off()
        else:
            ax = fig.add_subplot(111, projection='3d')
            ax.scatter(self.transformedData[:,0], self.transformedData[:,1], self.transformedData[:,2])
            ax.azim = azim
            ax.elev = elev
            ax.set_axis_off()

        if(fileName != ""):
            if(all):
                fig.set_size_inches(42,12)
            else:
                fig.set_size_inches(12,12)            
            plt.savefig(fileName,dpi=300)
            plt.close(fig)
        elif(show):
            plt.show()
            plt.close(fig)
            
        del fig
        
###############################################################################
###############################################################################
###############################################################################
###############################################################################
class ClusterBlob:
    """Main class for performing contig clustering
    
    All the bits and bobs you'll need to cluster and bin out 
    pre-transformed primary data
    """    
    def __init__(self, rowNames, secValues, secColors, transformedData, scaleFactor):
        # See DataTransformer for details about these variables
        self.contigNames = rowNames
        self.auxProfiles = secValues 
        self.auxColors = secColors
        self.transformedData = transformedData
        self.scaleFactor = scaleFactor

        # get enough memory for three heat maps
        self.imageMaps = np.zeros((3,self.scaleFactor,self.scaleFactor))
        self.blurredMaps = np.zeros((3,self.scaleFactor,self.scaleFactor))
        self.maxMaps = np.zeros((3,self.scaleFactor,self.scaleFactor))
        
        # we need a way to reference from the imageMaps back onto the transformed data
        self.mappedIndicies = {}
        self.binnedIndicies = {}

        # store our bins
        self.numBins = 0
        self.bins = {}
        
        # housekeeping / parameters
        self.roundNumber = 0            # how many times have we done this?
        self.span = 30                 # amount we can travel about when determining "hot spots"

        # When blurring the raw image maps I chose a radius to suit my data, you can vary this as you like
        self.blurRadius = 12
        self.auxWobble = 0.1            # amount the sec data can move about and still be in the same cluster
        
        self.imageCounter = 1           # when we print many images

    def clusterPoints(self, plotFileName=""):
        """Process contigs and form bins"""
        #
        # First we need to find the centers of each blob.
        # We can make a heat map and look for hot spots
        #
        self.populateImageMaps()
                        
        while(True):
        #for i in range(0,10):
            # apply a gaussian blur to each image map to make hot spots
            # stand out more from the background 
            self.blurMaps()
    
            # now search for the "hottest" spots on the blurred map
            # this is a new bin centroid
            (sec_centroid, center_indicies, max_blur_value) = self.findNewClusterCenter()
            if(-1 == sec_centroid):
                break
            else:
                # make sure we got something
                self.roundNumber += 1
                
                # time to make a bin
                self.numBins += 1
                bin = Bin(center_indicies, self.auxProfiles, self.numBins)
                self.bins[self.numBins] = bin
                bin.makeBinDist(self.transformedData, self.auxProfiles)                
                bin.plotBin(self.transformedData, self.auxColors, fileName="Image_"+str(self.imageCounter), tag="Initial")
                self.imageCounter += 1
        
                # make the bin more gooder
                bin.recruit(self.transformedData, self.auxProfiles, self.mappedIndicies, self.binnedIndicies)
                
                # Plots
                #bin.printContents()
                bin.plotBin(self.transformedData, self.auxColors, fileName="Image_"+str(self.imageCounter), tag="Recruited")
                self.imageCounter += 1
                print bin.dumpContigIDs(self.contigNames)

                self.plotHeat("3X3_"+str(self.roundNumber)+".png", max=max_blur_value)
                
                # append this bins list of mapped indicies to the main list
                self.updatePostBin(bin)

    def populateImageMaps(self):
        """Load the transformed data into the main image maps"""
        # reset these guys... JIC
        self.imageMaps = np.zeros((3,self.scaleFactor,self.scaleFactor))
        self.mappedIndicies = {}
        
        # add to the grid wherever we find a contig
        index = -1
        for point in np.around(self.transformedData):
            index += 1

            # can only bin things once!
            if index not in self.binnedIndicies:
                # readability
                px = point[0]
                py = point[1]
                pz = point[2]
                
                # add to the index dict so we can relate the 
                # map back to individual points later
                if (px,py,pz) in self.mappedIndicies:
                    self.mappedIndicies[(px,py,pz)].append(index)
                else:
                    self.mappedIndicies[(px,py,pz)] = [index]
                
                # now increment in the grid
                # for each point we encounter we incrmement
                # it's position + the positions to each side
                # and touching each corner
                self.incrementAboutPoint(0, px, py)
                self.incrementAboutPoint(1, self.scaleFactor-1-pz, py)
                self.incrementAboutPoint(2, self.scaleFactor-1-pz, self.scaleFactor-1-px)

    def updatePostBin(self, bin):
        """Update data structures after assigning contigs to a new bin"""
        for index in bin.indicies:
            self.binnedIndicies[index] = True
            
            # now update the image map, decrement
            point = np.around(self.transformedData[index])
            # readability
            px = point[0]
            py = point[1]
            pz = point[2]
            self.decrementAboutPoint(0, px, py)
            self.decrementAboutPoint(1, self.scaleFactor-1-pz, py)
            self.decrementAboutPoint(2, self.scaleFactor-1-pz, self.scaleFactor-1-px)

    def incrementAboutPoint(self, index, px, py, valP=1, valS=0.6, valC=0.2 ):
        """Increment value at a point in the 2D image maps
        
        Increment point by valP, increment neighbouring points at the
        sides and corners of the target point by valS and valC
        """
        if px > 0:
            if py > 0:
                self.imageMaps[index,px-1,py-1] += valC      # Top left corner
            self.imageMaps[index,px-1,py] += valS            # Top
            if py < self.scaleFactor-1:             
                self.imageMaps[index,px-1,py+1] += valC      # Top right corner

        if py > 0:
            self.imageMaps[index,px,py-1] += valS            # Left side
        self.imageMaps[index,px,py] += valP                  # Point
        if py < self.scaleFactor-1:             
            self.imageMaps[index,px,py+1] += valS            # Right side

        if px < self.scaleFactor-1:
            if py > 0:
                self.imageMaps[index,px+1,py-1] += valC      # Bottom left corner
            self.imageMaps[index,px+1,py] += valS            # Bottom
            if py < self.scaleFactor-1:             
                self.imageMaps[index,px+1,py+1] += valC      # Bottom right corner

    def decrementAboutPoint(self, index, px, py, valP=1, valS=0.6, valC=0.2 ):
        """Decrement value at a point in the 2D image maps"""
        if px > 0:
            if py > 0:
                self.imageMaps[index,px-1,py-1] -= valC      # Top left corner
                if self.imageMaps[index,px-1,py-1] < np.finfo(float).eps:
                    self.imageMaps[index,px-1,py-1] = 0
                
            self.imageMaps[index,px-1,py] -= valS            # Top
            if self.imageMaps[index,px-1,py] < np.finfo(float).eps:
                self.imageMaps[index,px-1,py] = 0
            if py < self.scaleFactor-1:             
                self.imageMaps[index,px-1,py+1] -= valC      # Top right corner
                if self.imageMaps[index,px-1,py+1] < np.finfo(float).eps:
                    self.imageMaps[index,px-1,py+1] = 0
                

        if py > 0:
            self.imageMaps[index,px,py-1] -= valS            # Left side
            if self.imageMaps[index,px,py-1] < np.finfo(float).eps:
                self.imageMaps[index,px,py-1] = 0
            
        self.imageMaps[index,px,py] -= valP                  # Point
        if self.imageMaps[index,px,py] < np.finfo(float).eps:
            self.imageMaps[index,px,py] = 0
        if py < self.scaleFactor-1:             
            self.imageMaps[index,px,py+1] -= valS            # Right side
            if self.imageMaps[index,px,py+1] < np.finfo(float).eps:
                self.imageMaps[index,px,py+1] = 0

        if px < self.scaleFactor-1:
            if py > 0:
                self.imageMaps[index,px+1,py-1] -= valC      # Bottom left corner
                if self.imageMaps[index,px+1,py-1] < np.finfo(float).eps:
                    self.imageMaps[index,px+1,py-1] = 0
            self.imageMaps[index,px+1,py] -= valS            # Bottom
            if self.imageMaps[index,px+1,py] < np.finfo(float).eps:
                self.imageMaps[index,px+1,py] = 0
            if py < self.scaleFactor-1:             
                self.imageMaps[index,px+1,py+1] -= valC      # Bottom right corner
                if self.imageMaps[index,px+1,py+1] < np.finfo(float).eps:
                    self.imageMaps[index,px+1,py+1] = 0

    def incrementAboutPoint3D(self, workingBlock, px, py, pz, vals=(6.4,4.9,2.5,1.6)):
        """Increment a point found in a 3D column
        
        used when finding the centroid of a hot area
        update the 26 points which surround the centre point
        z spans the height of the entire column, x and y have been offset to
        match the column subspace
        """
        
        # top slice
        if pz < self.scaleFactor-1:
            self.subIncrement3D(workingBlock, px, py, pz+1, vals, 1)
        
        # center slice
        self.subIncrement3D(workingBlock, px, py, pz, vals, 0)
        
        # bottom slice
        if pz > 0:
            self.subIncrement3D(workingBlock, px, py, pz-1, vals, 1)
        
    def subIncrement3D(self, workingBlock, px, py, pz, vals, offset):
        """AUX: Called from incrementAboutPoint3D does but one slice"""       
        # get the size of the working block
        shape = np.shape(workingBlock)
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
        self.blurredMaps = np.zeros((3,self.scaleFactor,self.scaleFactor))
        self.maxMaps = np.zeros((3,self.scaleFactor,self.scaleFactor))
        
        for i in range (0,3): # top, front and side
            self.blurredMaps[i,:,:] = ndi.gaussian_filter(self.imageMaps[i,:,:]**0.5, (self.blurRadius,self.blurRadius)) 

        # there's still a lot of background signal to remove
        # we wish to remove 90% of the data, this will leave just the really hot spots
        # Make a histogram of the data (use the top face)
        [vals,points] = np.histogram(np.reshape(self.blurredMaps[0,:,:], (self.scaleFactor, self.scaleFactor,1)), 50)
        total = np.sum(vals)*0.80
        lop_index = 1       # where we lop off the low values
        for val in vals:
            total -= val
            if total <= 0:
                break
            lop_index += 1
        lop_val = points[lop_index]

        # remove these low values and down normalise so that the largest value is equal to exactly 1
        for i in range (0,3): # top, front and side
            self.blurredMaps[i,:,:] = np.where(self.blurredMaps[i,:,:] >= lop_val, self.blurredMaps[i,:,:], 0)/lop_val

    def findNewClusterCenter(self):
        """Find a putative cluster"""
        # we work from the top view as this has the base clustering
        max_index = np.argmax(self.blurredMaps[0])
        #max_index = np.argmax(self.imageMaps[0])
        max_value = self.blurredMaps[0].ravel()[max_index]
        #max_value = self.imageMaps[0].ravel()[max_index]
        max_x = int(max_index/self.scaleFactor)
        max_y = max_index - self.scaleFactor*max_x
        max_z = -1

        # store all points in the path here
        center_indicies = np.array([])

        print "##############################################\n##############################################"
        print "MV",max_value,"(",max_index,") @ (",max_x,",",max_y,")"        
        
        this_span = int(1.5 * self.span)
        span_len = 2*this_span+1
        
        # work out the region this max value lives in
        x_density = np.zeros(span_len)
        x_offset = max_x - this_span
        
        y_density = np.zeros(span_len)
        y_offset = max_y - this_span
        
        self.plotRegion(max_x,max_y,max_z, fileName="Image_"+str(self.imageCounter), tag="column", column=True)
        self.imageCounter += 1

        # make a 3d grid to hold the values
        working_block = np.zeros((span_len, span_len, self.scaleFactor))
        
        # go through the entire column
        x_lower = max_x-this_span
        x_upper = max_x+this_span+1
        y_lower = max_y-this_span
        y_upper = max_y+this_span+1
        for z in range(0, self.scaleFactor):
            realz = self.scaleFactor-z
            for x in range(x_lower, x_upper):
                for y in range(y_lower, y_upper):
                    # check that the point is real and that it has not yet been binned
                    if((x,y,realz) in self.mappedIndicies):
                        for index in self.mappedIndicies[(x,y,realz)]:
                            if index not in self.binnedIndicies:
                                # this is an unassigned point. 
                                self.incrementAboutPoint3D(working_block, x-x_lower, y-y_lower, z)

        # blur and find the highest value
        bwb = ndi.gaussian_filter(working_block, self.blurRadius)
        
        densest_index = np.unravel_index(np.argmax(bwb), (np.shape(bwb)))
        max_x = densest_index[0] + x_lower
        max_y = densest_index[1] + y_lower
        max_z = densest_index[2]
       
        print "densest at: ",densest_index,"(",max_x,max_y,max_z,")"

        if(False):
            plot_array = np.array([])
            pindex = 0
            for x in range(0, span_len):
                for y in range(0, span_len):
                    for z in range(0, self.scaleFactor):
                        if(working_block[x,y,z] > 0):
                            plot_array = np.append(plot_array, [x])
                            plot_array = np.append(plot_array, [y])
                            plot_array = np.append(plot_array, [z])
                            pindex += 1
    
            plot_array =np.reshape(plot_array, (pindex, 3))                     
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')
            ax.scatter(plot_array[:,0], plot_array[:,1], plot_array[:,2], marker='.')#, edgecolors=plot_cols, c=plot_cols)
            plt.show()
            del fig

        self.plotRegion(max_x,max_y,max_z, fileName="Image_"+str(self.imageCounter), tag="first approx")
        self.imageCounter += 1

        # now get the basic color of this dense point
        center_values = np.array([])
        for z in range(max_z-self.span, max_z+self.span+1):
            realz = self.scaleFactor-z
            for x in range(max_x-self.span, max_x+self.span+1):
                for y in range(max_y-self.span, max_y+self.span+1):
                    if((x,y,realz) in self.mappedIndicies):
                        for index in self.mappedIndicies[(x,y,realz)]:
                            if index not in self.binnedIndicies:
                                center_values = np.append(center_values, self.auxProfiles[index])

        cf = CenterFinder()
        sec_centroid = cf.findArrayCenter(center_values)                            
        sec_lower = sec_centroid - self.auxWobble
        sec_upper = sec_centroid + self.auxWobble

        # now scoot out around this point and soak up similar points
        # get all the real indicies of these points so we can use them in
        # the primary data map
        for z in range(max_z-self.span, max_z+self.span+1):
            realz = self.scaleFactor-z
            for x in range(max_x-self.span, max_x+self.span+1):
                for y in range(max_y-self.span, max_y+self.span+1):
                    # check that the point is real and that it has not yet been binned
                    if((x,y,realz) in self.mappedIndicies):
                        for index in self.mappedIndicies[(x,y,realz)]:
                            if index not in self.binnedIndicies:
                                if(self.auxProfiles[index] > sec_lower and self.auxProfiles[index] < sec_upper):
                                    self.maxMaps[0,x,y] = self.blurredMaps[0,x,y]
                                    self.maxMaps[1,z,y] = self.blurredMaps[1,z,y]
                                    self.maxMaps[2,z,self.scaleFactor-x] = self.blurredMaps[1,z,self.scaleFactor-x]                                
                                    # add only once!
                                    if(index not in center_indicies):
                                        # bingo!
                                        center_indicies = np.append(center_indicies, index)
        if(np.size(center_indicies) > 0):
            return (sec_centroid, center_indicies, max_value)
        
        center_indicies = np.array([])
            
        return (sec_centroid, center_indicies, -1)

    def Ablur(self, blur, density, incAtPoint, index, offset, size):
        """AUX: Used when finding the densest point in a small block"""
        point = index + offset;
        if(point >= 0 and point < size):
            blur[point] += incAtPoint[abs(offset)] * density[index]
    
#------------------------------------------------------------------------------
# IO and IMAGE RENDERING 
    def plotRegion(self, px, py, pz, fileName="", tag="", column=False):
        """Plot the region surrounding a point """
        disp_vals = np.array([])
        disp_cols = np.array([])
        num_points = 0
        # plot all points within span
        z_lower = pz-self.span
        z_upper = pz+self.span
        if(column):
            z_lower = 0
            z_upper = self.scaleFactor - 1
        
        for z in range(z_lower, z_upper):
            realz = self.scaleFactor - z 
            for x in range(px-self.span, px+self.span):
                for y in range(py-self.span, py+self.span):
                    if((x,y,realz) in self.mappedIndicies):
                        for index in self.mappedIndicies[(x,y,realz)]:
                            if index not in self.binnedIndicies:
                                num_points += 1
                                disp_vals = np.append(disp_vals, self.transformedData[index])
                                disp_cols = np.append(disp_cols, self.auxColors[index])
        
        # make a black mark at the max values
        small_span = self.span/2
        for z in range(pz-small_span, pz+small_span):
            realz = self.scaleFactor - z 
            for x in range(px-small_span, px+small_span):
                for y in range(py-small_span, py+small_span):
                    if((x,y,realz) in self.mappedIndicies):
                        for index in self.mappedIndicies[(x,y,realz)]:
                            if index not in self.binnedIndicies:
                                num_points += 1
                                disp_vals = np.append(disp_vals, self.transformedData[index])
                                disp_cols = np.append(disp_cols, colorsys.hsv_to_rgb(0,0,0))
        # reshape
        disp_vals = np.reshape(disp_vals, (num_points, 3))
        disp_cols = np.reshape(disp_cols, (num_points, 3))
        
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        cm = mpl.colors.LinearSegmentedColormap('my_colormap', disp_cols, 1024)
        result = ax.scatter(disp_vals[:,0], disp_vals[:,1], disp_vals[:,2], edgecolors=disp_cols, c=disp_cols, cmap=cm, marker='.')
        title = str.join(" ", ["Focus at: (",str(px), str(py), str(self.scaleFactor - pz),")\n",tag])
        plt.title(title)
      
        if(fileName != ""):
            fig.set_size_inches(6,6)
            plt.savefig(fileName,dpi=300)
        elif(show):
            plt.show()
        
        plt.close(fig)
        del fig
    
    def plotHeat(self, fileName = "", max=-1):
        """Print the main heat maps
        
        Useful for debugging
        """
        fig = plt.figure()
        images = []

        ax = fig.add_subplot(231)
        images.append(ax.imshow(self.blurredMaps[0,:,:]**0.5))
        if(max > 0):
            title = str.join(" ", ["Max value:",str(max)])
            plt.title(title)
        ax = fig.add_subplot(232)
        images.append(ax.imshow(self.blurredMaps[1,:,:]**0.5))
        ax = fig.add_subplot(233)
        images.append(ax.imshow(self.blurredMaps[2,:,:]**0.5))

        ax = fig.add_subplot(234)
        images.append(ax.imshow(self.imageMaps[0,:,:]**0.5))
        ax = fig.add_subplot(235)
        images.append(ax.imshow(self.imageMaps[1,:,:]**0.5))
        ax = fig.add_subplot(236)
        images.append(ax.imshow(self.imageMaps[2,:,:]**0.5))
        
        if(fileName != ""):
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
class Bin:
    """Class for managing collections of contigs
    
    To (perhaps) simplify things think of a "bin" as an index into the
    column names array. The ClusterBlob has a list of bins which it can
    update etc...
    """
    def __init__(self, indicies, secValues, id, pritol=3, sectol=3):
        self.id = id
        self.indicies = indicies           # all the indicies belonging to this bin
        self.binSize = self.indicies.shape[0]
        
        # we need some objects to manage the distribution of contig proerties
        self.mean = np.zeros((4))
        self.stdev = np.zeros((4))
        self.priTolerance = pritol
        self.auxTolerance = sectol
        self.lowerLimits = np.zeros((4)) # lower and upper limits based on tolerance
        self.upperLimits = np.zeros((4))

#------------------------------------------------------------------------------
# Stats and properties 
         
    def findBinCenterIndex(self, secValues):
        """Find the center of a bin"""
        min_diff = 100000
        best_index = -1
        for index in self.indicies:
            diff = abs(secValues[index] - self.auxCentroid)
            if(diff < min_diff):
                min_diff = diff
                best_index = index
        return best_index

    def clearBinDist(self):
        """Clear any set distribution statistics"""
        self.mean = np.zeros((4))
        self.stdev = np.zeros((4))
        self.lowerLimits = np.zeros((4))
        self.upperLimits = np.zeros((4))
        
    def makeBinDist(self, transformedData, secValues):
        """Determine the distribution of the points in this bin
        
        The distribution is largely normal, except at the boundaries.
        """
        self.clearBinDist()
        
        # get the values of interest
        working_array = np.zeros((self.binSize,4))
        outer_index = 0
        for index in self.indicies:
            for i in range(0,3):
                working_array[outer_index][i] = transformedData[index][i]
            working_array[outer_index][3] = secValues[index]
            outer_index += 1
            
        # calculate the mean and srdev 
        self.mean = np.mean(working_array,axis=0)
        self.stdev = np.std(working_array,axis=0)
            
        # set the acceptance ranges
        self.makeLimits()
        
    def makeLimits(self, pt=-1, st=-1):
        """Set inclusion limits based on mean, variance and tolerance settings"""
        if(-1 == pt):
            pt=self.priTolerance
        if(-1 == st):
            st=self.auxTolerance
        for i in range(0,3):
            self.lowerLimits[i] = int(self.mean[i] - pt * self.stdev[i])
            self.upperLimits[i] = int(self.mean[i] + pt * self.stdev[i]) + 1  # so range will look neater!
        self.lowerLimits[3] = self.mean[3] - st * self.stdev[3]
        self.upperLimits[3] = self.mean[3] + st * self.stdev[3]

#------------------------------------------------------------------------------
# Grow the bin 
    
    def recruit(self, transformedData, secValues, mappedIndicies, binnedIndicies):
        """Iteratively grow the bin"""
        self.makeBinDist(transformedData, secValues)
        print "--------------------------"
        print "BIN:", self.id, "size:", self.binSize

        # save these
        pt = self.priTolerance
        st = self.auxTolerance

        self.binSize = self.indicies.shape[0]
        self.makeBinDist(transformedData, secValues)
        num_recruited = self.recruitRound(transformedData, secValues, mappedIndicies, binnedIndicies) 
        while(num_recruited > 0):
            print "REC:", num_recruited
            # reduce these to force some kind of convergence
            self.priTolerance *= 0.8
            self.auxTolerance *= 0.8
            # fix these
            self.binSize = self.indicies.shape[0]
            self.makeBinDist(transformedData, secValues)
            # print for fun
            #self.printContents()
            # go again
            num_recruited = self.recruitRound(transformedData, secValues, mappedIndicies, binnedIndicies)
        
        self.priTolerance = pt
        self.auxTolerance = st
        
        # finally, fix this guy
        print "Expanded to:", self.binSize
        
    def recruitRound(self, transformedData, secValues, mappedIndicies, binnedIndicies):
        """Recruit more points in from outside the current blob boundaries"""
        num_recruited = 0
        for x in range(int(self.lowerLimits[0]), int(self.upperLimits[0])):
            for y in range(int(self.lowerLimits[1]), int(self.upperLimits[1])):
                for z in range(int(self.lowerLimits[2]), int(self.upperLimits[2])):
                    if((x,y,z) in mappedIndicies):
                        for index in mappedIndicies[(x,y,z)]:
                            if (index not in binnedIndicies) and (index not in self.indicies):
                                if(secValues[index] >= self.lowerLimits[3] and secValues[index] <= self.upperLimits[3]):
                                    self.indicies = np.append(self.indicies,index)
                                    num_recruited += 1
        return num_recruited

#------------------------------------------------------------------------------
# IO and IMAGE RENDERING 
#
    def plotBin(self, transformedData, secColors, fileName="", tag=""):
        """Plot a bin"""
        disp_vals = np.array([])
        disp_cols = np.array([])
        num_points = 0
        for index in self.indicies:
            num_points += 1
            disp_vals = np.append(disp_vals, transformedData[index])
            disp_cols = np.append(disp_cols, secColors[index])

        # make a black mark at the max values
        self.makeLimits(pt=1, st=1)
        px = int(self.mean[0])
        py = int(self.mean[1])
        pz = int(self.mean[2])
        num_points += 1
        disp_vals = np.append(disp_vals, [px,py,pz])
        disp_cols = np.append(disp_cols, colorsys.hsv_to_rgb(0,0,0))
        
        # fix these
        self.makeLimits()
        
        # reshape
        disp_vals = np.reshape(disp_vals, (num_points, 3))
        disp_cols = np.reshape(disp_cols, (num_points, 3))

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter(disp_vals[:,0], disp_vals[:,1], disp_vals[:,2], edgecolors=disp_cols, c=disp_cols, marker='.')
        title = str.join(" ", ["Bin:",str(self.id),"Focus at: (",str(px), str(py), str(pz),")\n",tag,"\nContains:",str(self.binSize),"contigs"])
        plt.title(title)
        
        if(fileName != ""):
            fig.set_size_inches(6,6)
            plt.savefig(fileName,dpi=300)
        elif(show):
            plt.show()
            
        plt.close(fig)
        del fig
    
    def printContents(self):
        """Dump the contents of the object"""
        print "--------------------------------------"
        print "Bin:", self.id
        print "Bin size:", self.binSize
        print "Mean:", self.mean
        print "Stdev:", self.stdev
        print "P Tol:", self.priTolerance
        print "S Tol:", self.auxTolerance
        print "Lower limts:", self.lowerLimits
        print "Upper limits:", self.upperLimits
        print "--------------------------------------"
    
    def dumpContigIDs(self, rowNames):
        """Print out the contigIDs"""
        from cStringIO import StringIO
        file_str = StringIO()
        for index in self.indicies:
            file_str.write(rowNames[index]+"\t")
        return file_str.getvalue()

###############################################################################
###############################################################################
###############################################################################
###############################################################################
class CenterFinder:
    """When a plain old mean won't cut it

    Uses a bouncing ball algorithm. Imagine walking along a "path",
    (through the array) hitting a ball into the air each time you
    come across a value. Gravity is bringing the ball down. If we plot
    the height of the ball vs array index then the highest the ball
    reaches is the index in the center of the densest part of the array 
    """
    def __init__(self): pass
    
    def findArrayCenter(self, vals):
        """Find the center of the numpy array vals"""
        # parameters
        current_val_max = -1
        delta = 0
        bounce_amount = 0.1
        height = 0
        last_val= 0

        working = np.array([])
        final_index = -1
        # run through in one direction
        vals = np.sort(vals)
        for val in vals:
            # calculate delta
            delta = val - last_val
            # reduce the current value according to the delta value
            height = self.reduceViaDelta(height, bounce_amount, delta)
            # bounce the ball up
            height += bounce_amount
            
            # store the height
            working = np.append(working, height)
            final_index += 1

            # save the last val            
            last_val = val

        current_val_max = -1
        height = 0
        last_val = 0
        # run through in the reverse direction
        vals = vals[::-1]
        for val in vals:
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
        
        max_index = np.argmax(working)
        vals = np.sort(vals)
        max_value = vals[max_index]
         
        return max_value
    
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
