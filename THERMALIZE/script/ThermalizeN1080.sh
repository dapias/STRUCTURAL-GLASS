#!/bin/bash
#
#A partire dalle configurazioni calde ne creo di piu` fredde

#
# QUEUE PROPERTIES 
#
readonly PROC_TAG="rt"
readonly USERNAME=`whoami`

readonly SYSTEM="PennPuter"
#readonly SYSTEM="talapas"

queue=gpu

#PARAMETERS THAT SHOULD BE AT THE BEGINNING
nsam=4
let nsamm1=$nsam-1
dt=0.0025
backupFreq=`echo 10/$dt|bc`
hottestT=10.0
TLIST="0.466" # 0.6"

#DIRECTORIES
scriptDIR=$PWD
thermDIR=$PWD/..
rootDIR=$PWD/../..
exeDIR=$thermDIR/progs
workDIR=$rootDIR/OUTPUT
mkdir -p $workDIR
cd $workDIR


#Range of temperatures
for T in $(echo $TLIST)
do
    mkdir -p T$T
    cd T$T
    echo "T = $T"
    
    for Natoms in 1080
    do
	mkdir -p N$Natoms
	cd N$Natoms
	echo "Natoms = $Natoms"
	
	inistateDIR=$workDIR/INITIAL-STATES/N$Natoms
	hottestTDIR=$workDIR/T$hottestT/N$Natoms
	
	
	for isam in $(seq 0 $nsamm1)
	do
	    echo "isam: $isam"
	    mkdir -p S$isam
	    cd S$isam
	    
	    seed=$(od -vAn -N4 -tu4 < /dev/urandom)
	    thermConfName=thermalized.gsd
	    case $T in
		10.0)  totMDsteps=$(echo 0.5*10^3/$dt|bc); thermostat=MB;  tauT=1.0; heavyTrajFreq=0;                       initConf=$inistateDIR/initIS.gsd;;
		0.6)   totMDsteps=$(echo 2*10^4/$dt  |bc); thermostat=NVT; tauT=0.1; heavyTrajFreq=`echo $totMDsteps/|bc`; initConf=$hottestTDIR/S$isam/$thermConfName;;
		0.466) totMDsteps=$(echo 5*10^5/$dt  |bc); thermostat=NVT; tauT=0.1; heavyTrajFreq=`echo $totMDsteps/10|bc`; initConf=$hottestTDIR/S$isam/$thermConfName;;
		*) echo "How many steps for this temperature?";exit;;
	    esac
	    
	    echo $initConf
	    
	    #If thermalized configuration already exists, then continue from there (to be able to make longer thermalization runs)
	    if [ -e $thermConfName ] ;then
		initConf=$thermConfName
		echo "Continuing run from $initConf"
	    else
		echo "Starting run from $initConf"
	    fi
	    
	    #It may happen that no initial configuration is available.
	    #In that case, give a warning and skip sample
	    if [ ! -f $initConf ]; then
		echo "WARNING: $initconf does not exist"
		cd ..; continue
	    fi
	    
	    #
	    # Run Python script
	    #
	    if [ $SYSTEM == "PennPuter" ]; then
		echo `whoami`$USERNAME@`uname -n` > thermalized.time
		time (python $exeDIR/ReadAndThermalize.py --user="$initConf -N$Natoms -s$seed -T$T -t$totMDsteps --tauT=$tauT --dt=$dt --thermostat=$thermostat --backupFreq=$backupFreq --heavyTrajFreq=$heavyTrajFreq --addsteps=False"  2>&1) 2>>thermalized.time &
	    elif [ $SYSTEM == "talapas" ]; 
	    then
		nombre=N${Natoms}${PROC_TAG}T${T}i${isam}
		if [ 0 == `squeue -u$USERNAME -n $nombre|grep $USERNAME|wc -l` ]
		then
		    echo sbatch --job-name=$nombre -p $queue --export=exeDIR=$exeDIR,initConf=$initConf,Natoms=$Natoms,seed="${seed}",T=$T,totMDsteps=$totMDsteps,tauT=$tauT,dt=$dt,thermostat=$thermostat,backupFreq=$backupFreq,heavyTrajFreq=$heavyTrajFreq $scriptDIR/Thermalize.sbatch
		    sbatch --job-name=$nombre --export=exeDIR=$exeDIR,initConf=$initConf,Natoms=$Natoms,seed="${seed}",T=$T,totMDsteps=$totMDsteps,tauT=$tauT,dt=$dt,thermostat=$thermostat,backupFreq=$backupFreq,heavyTrajFreq=$heavyTrajFreq $scriptDIR/Thermalize.sbatch
		fi
	    else
		echo "SYSTEM=$SYSTEM not recognized"
		exit
	    fi
	    echo ""
	    cd ..
	done #isam
	cd ..
    done #Natoms
    cd ..
    wait
done #T
cd ..
