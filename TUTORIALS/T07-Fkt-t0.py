#!/usr/bin/python
################################################################
#
# DESCRIPTION
# This example reads a trajectory from a .gsd file, and calculates the
# self-intermediate scattering function for several couples of times
# t0 and t, that are initially set in a list.
#
# To launch a simulation:
# python T7-Fkt-t0.py trajectory.gsd
#
# For example:
# python T7-Fkt-t0.py ./test-output/trajectory.gsd
#
################################################################

from __future__ import print_function #for compatibility with python3.5
import sys #this has some system tools like sys.exit() that can be useful
import numpy as np #Handles some mathematical operations
import gsd.pygsd
import gsd.hoomd
import matplotlib.pyplot as plt
from numba import jit

################################################################
#
# FUNCTIONS THAT WOULD GO IN A SEPARATE MODULE
# 
################################################################

def PeriodicSquareDistance(vec_a, vec_b, box_size):
# This function measures the distance between two lists of points, vec_a and vec_b,
# that can be vectors.
# box_size can be np.array([Lx,Ly,Lz]) or even just L
    delta = np.abs(vec_a - vec_b) #substraction and abs are done component by component
    delta = np.where(delta > 0.5 * box_size, delta - box_size, delta) #condition==True ? return second arg :otherwise return third
    return (delta ** 2).sum(axis=-1)

def PeriodicDisplacement(vec_a, vec_b, box_size):
# This function measures the vector displacement between two lists of positions, vec_a and vec_b,
# box_size can be np.array([Lx,Ly,Lz]) or even just L
    # First we substract one to the other
    delta = vec_a - vec_b
    #Then we apply periodic boundary conditions through a double ternary
    return np.where(delta > 0.5 * box_size, delta - box_size, np.where(delta < -0.5 * box_size, delta+box_size, delta))


def PeriodicDistance(vec_a, vec_b, box_size):
    return np.sqrt(PeriodicSquareDistance(vec_a, vec_b, box_size))

def CalculateFkt(old_pos, new_pos, box_size):
    all_displacements=PeriodicSquareDistance(old_pos, new_pos, box_size)
    raise SystemExit #the function is not ready
    return all_displacements.sum()

@jit (nogil=True, nopython=True)
def getKSets_function(nx,ny,nz, it):
    if it==0:
        return np.array([nx,ny,nz])#,dtype=float)
    if it==1:
        return np.array([nz,nx,ny])#,dtype=float)
    if it==2:
        return np.array([ny,nz,nx])#,dtype=float)
    if it==3:
        return np.array([nx,nz,ny])#,dtype=float)
    if it==4:
        return np.array([nz,ny,nx])#,dtype=float)
    if it==5:
        return np.array([ny,nx,nz])#,dtype=float)

@jit (nogil=True, nopython=False)
def ComputeFkt(NX, NY, NZ, L, displacements):
    #Given the displacement vector and the wave numbers, we calculate the value of Fkt
    Fk_Deltat = np.zeros( len(displacements), dtype=np.complex128)
    numk=48 #2(+/-) x 3(dimensions) x 6(permutations) = 48
    for nx in [NX,-NX]:
        for ny in [NY,-NY]:
            ## note that we could spare this last loop and double the weight of these z-conributions and take real part.. but it's not elegant.
            for nz in [NZ,-NZ]:
                for k_set_index in range(6):
                    k_vector = getKSets_function(nx,ny,nz,k_set_index)
                    Fk_Deltat += np.exp( (2.0j*np.pi/L) * np.sum(k_vector*displacements,1) ) 
                    ## remember that Fk_Deltat is an array (size Natoms)
    #We should check that the imaginary part of Fk is zero
    return np.real(Fk_Deltat).sum()/numk

################################################################
#
# READ ARGUMENTS
# 
################################################################
if len(sys.argv)==2:
    filename = sys.argv[1] #Name of the file with the trajectory
else:
    print("Launch as:")
    print(sys.argv[0]," configuration.gsd")
print(filename)
every_forMemory = 1

################################################################
#
# READ TRAJECTORY
# 
################################################################
with open(filename, 'rb') as flow:
    HoomdFlow = gsd.pygsd.GSDFile(flow)
    hoomdTraj = gsd.hoomd.HOOMDTrajectory(HoomdFlow);
    s0=hoomdTraj.read_frame(0) #This is a snapshot of the initial configuration (frame zero)
    Natoms=s0.particles.N
    boxParams=s0.configuration.box
    L=boxParams[0]
    if boxParams[0] != boxParams[1] or  boxParams[1]!= boxParams[2] or  boxParams[0]!= boxParams[2]:
        print('box dimensions are : ', boxParams[0])
        print('and are not supported (only isotropic systems supported)')
        raise SystemExit
    
    Nframes = len(hoomdTraj)
    trajDuration = Nframes/every_forMemory
    print('there are Nframes=', Nframes, 'in the file, but we only use trajDuration=',trajDuration, ' of them.')

    #Now we create a trajectory array, containing the positions of the particles at each t
    trajectory = np.zeros((trajDuration,Natoms,3))
    timestep=np.zeros(trajDuration)
    for time in range(0, trajDuration, 1):
        ## we only look 1 frame every "every_forMemory" frame, to save memory: 
        trajectory[time] = (hoomdTraj[time*every_forMemory].particles.position) # [selectedAtoms]
        timestep[time] = hoomdTraj[time*every_forMemory].configuration.step
    HoomdFlow.close()
    
print('Shape of the trajectory array (times, particles, dimensions):', np.shape(trajectory))

################################################################
# 
# TIME PARAMETERS
#
################################################################
#When I use times, here, I am actually referring to the frames
nt=int(trajDuration*0.25) #maximum difference between t0 and t
t0list=np.arange(0,trajDuration,0.1*trajDuration,dtype=np.int64)
nt0=len(t0list)

################################################################
# 
# CALCULATE Fk(t0,t)
#
################################################################
box_size=np.array([L,L,L])
times=np.zeros(nt*nt0)
t0long=np.zeros(nt*nt0)
i0list=np.zeros(nt*nt0)
ilist=np.zeros(nt*nt0)
Fk=np.zeros(nt*nt0,dtype=np.double)

for i0 in range(0,nt0):
    t0=t0list[i0]
    oldPositions=np.array(trajectory[t0])
    for i in range(0,nt):
        t=t0+i*every_forMemory
        if t>=trajDuration:
            continue
        newPositions=np.array(trajectory[t])
        i0list[i0*nt+i]=i0 #These 4 lists are just to make the data file with savetxt
        ilist[i0*nt+i]=i
        times[i0*nt+i]=t
        t0long[i0*nt+i]=t0
        all_displacements=PeriodicDisplacement(newPositions, oldPositions, box_size)
        Fk[i0*nt+i]=ComputeFkt(4, 6, 8, L, all_displacements)/Natoms
        
################################################################
# 
# FIGURES
#
################################################################

#I merge together the lists, to produce a nice text output
output_Fk=np.column_stack((i0list,ilist,t0long, times, Fk))
np.savetxt('./test-output/Fkt-t0.txt',output_Fk,fmt='%g %g %g %g %.14g',header="#1)i0 2)i 3)t0 4)t 5)Fk(t,t0)")









