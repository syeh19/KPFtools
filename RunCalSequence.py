#! /kroot/rel/default/bin/kpython3

'''Each class defined below is intended to encapsulate a simple operation. For
future compatibility with Keck DSI, they are formatted with pre_condition,
perform, and post_condition methods which are all wrapped in to an execute
method.

The pre and post conditions are there to capture checks before and after a
command is sent.  These can evolve and grow over time to catch or handle
errors.

The args passed to each class when executed will be replaced with a more formal
system under DSI.  For now this is a simple dictionary of values.  No attempt
to handle malformed arguments has been made -- they will cause problems if not
formatted properly.

The last class, RunCalSequence, sequences the other operations.  When called
from the terminal (e.g. `kpython3 RunCalSequence.py` or `./RunCalSequence.py`)
the `if __name__ == '__main__':` section will parse command line options and
pass them to RunCalSequence.
'''

import ktl

import argparse
import logging
from time import sleep
from pathlib import Path
import yaml


KPFError = Exception


##-------------------------------------------------------------------------
## Create logger object
##-------------------------------------------------------------------------
log = logging.getLogger('RunCalSequence')
log.setLevel(logging.DEBUG)
## Set up console output
LogConsoleHandler = logging.StreamHandler()
LogConsoleHandler.setLevel(logging.DEBUG)
LogFormat = logging.Formatter('%(asctime)s %(levelname)8s: %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')
LogConsoleHandler.setFormatter(LogFormat)
log.addHandler(LogConsoleHandler)
## Set up file output
# LogFileName = None
# LogFileHandler = logging.FileHandler(LogFileName)
# LogFileHandler.setLevel(logging.DEBUG)
# LogFileHandler.setFormatter(LogFormat)
# log.addHandler(LogFileHandler)


##-------------------------------------------------------------------------
## SetExptime
##-------------------------------------------------------------------------
class SetExptime():
    '''Sets the desired exposure time via the `kpfexpose.EXPOSURE` keyword
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        exptime = args.get('Exptime', None)
        if exptime is not None:
            log.info(f"  Setting exposure time to {exptime:.1f}")
            kpfexpose = ktl.cache('kpfexpose')
            kpfexpose['EXPOSURE'].write(exptime)


    def post_condition(self, args):
        exptime = args.get('exptime', None)
        if exptime is not None:
            kpfexpose = ktl.cache('kpfexpose')
            exptime_value = kpfexpose['EXPOSURE'].read()
            if abs(exptime_value - exptime) > 0.1:
                msg = (f"Final exposure time mismatch: "
                       f"{exptime_value:.1f} != {exptime:.1f}")
                log.error(msg)
                raise KPFError(msg)
        log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## StartExposure
##-------------------------------------------------------------------------
class StartExposure():
    '''Begins an triggered exposure by setting the `kpfexpose.EXPOSE` keyword
    to Start.  This will return immediately after.  Use commands like
    WaitForReadout or WaitForReady to determine when an exposure is done.
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        kpfexpose = ktl.cache('kpfexpose')
        expose = kpfexpose['EXPOSE']
        expose.monitor()
        if expose > 0:
            log.info(f"  Detector(s) are currently {expose} waiting for Ready")
            expose.waitFor('== 0',timeout=300)
        log.info(f"  Beginning Exposure")
        expose.write('Start')


    def post_condition(self, args):
        kpfexpose = ktl.cache('kpfexpose')
        exptime = kpfexpose['EXPOSURE'].read(binary=True)
        expose = kpfexpose['EXPOSE'].read()
        log.debug(f"    exposure time = {exptime:.1f}")
        log.debug(f"    status = {expose}")
        if exptime > 0.1:
            if expose not in ['Start', 'InProgress', 'End', 'Readout']:
                msg = f"Unexpected EXPOSE status = {expose}"
                log.error(msg)
                raise KPFError(msg)
        log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## WaitForReadout
##-------------------------------------------------------------------------
class WaitForReadout():
    '''Waits for the `kpfexpose.EXPOSE` keyword to be "Readout".  This will
    block until the camera enters the readout state.  Times out after waiting
    the current exposure time plus 10 seconds.
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        log.info(f"  Waiting for readout to begin")
        kpfexpose = ktl.cache('kpfexpose')
        exptime = kpfexpose['EXPOSURE'].read(binary=True)
        expose = kpfexpose['EXPOSE']
        expose.monitor()
        expose.waitFor('== 4',timeout=exptime+10)


    def post_condition(self, args):
        kpfexpose = ktl.cache('kpfexpose')
        expose = kpfexpose['EXPOSE']
        status = expose.read()
        if status != 'Readout':
            msg = f"Final detector state mismatch: {status} != Readout"
            log.error(msg)
            raise KPFError(msg)
        log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## WaitForReady
##-------------------------------------------------------------------------
class WaitForReady():
    '''Waits for the `kpfexpose.EXPOSE` keyword to be "Ready".  This will
    block until the camera is ready for another exposure.  Times out after
    waiting 60 seconds.
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        log.info(f"  Waiting for detectors to be ready")
        kpfexpose = ktl.cache('kpfexpose')
        expose = kpfexpose['EXPOSE']
        expose.monitor()
        expose.waitFor('== 0',timeout=60)


    def post_condition(self, args):
        kpfexpose = ktl.cache('kpfexpose')
        expose = kpfexpose['EXPOSE']
        status = expose.read()
        if status != 'Ready':
            msg = f"Final detector state mismatch: {status} != Ready"
            log.error(msg)
            raise KPFError(msg)
        log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## PowerOnCalSource
##-------------------------------------------------------------------------
class PowerOnCalSource():
    '''Powers on one of the cal lamps via the `kpfpower` keyword service.
    
    The mapping between lamp name and power outlet is hard coded for now.
    The only check on this is that the log message will include the name
    of the power outlet which has been powered on as read from the _NAME
    keyword for that outlet.  No automatic checking of the name is currently
    performed, the only check is if a human reads the log line.
    
    The current mapping only handles the following lamps:
    - U_gold
    - U_daily
    - Th_daily
    - Th_gold
    - BrdbandFiber
    '''
    def __init__(self):
        self.ports = {'EtalonFiber': None,
                      'BrdbandFiber': 'OUTLET_CAL2_2',
                      'U_gold': 'OUTLET_CAL2_7',
                      'U_daily': 'OUTLET_CAL2_8',
                      'Th_daily': 'OUTLET_CAL2_6',
                      'Th_gold': 'OUTLET_CAL2_5',
                      'SoCal-CalFib': None,
                      'LFCFiber': None,
                      }


    def pre_condition(self, args):
        pass


    def perform(self, args):
        kpfpower = ktl.cache('kpfpower')
        port = self.ports.get(args.get('lamp', None))
        if port is not None:
            port_name = kpfpower[f"{port}_NAME"].read()
            if kpfpower[port].read() == 'On':
                log.info(f"    Outlet {port} ({port_name}) is already On")
            else:
                log.info(f"    Unlocking {port} ({port_name})")
                kpfpower[f"{port}_LOCK"].write('Unlocked')
                log.info(f"    Turning on {port} ({port_name})")
                kpfpower[port].write('On')
                log.info(f"    Locking {port} ({port_name})")
                kpfpower[f"{port}_LOCK"].write('Locked')


    def post_condition(self, args):
        '''Verifies that the relevant power port is actually on.
        '''
        kpfpower = ktl.cache('kpfpower')
        port = self.ports.get(args.get('lamp', None))
        if port is not None:
            port_name = kpfpower[f"{port}_NAME"].read()
            log.info(f"    Reading {port} ({port_name})")
            state = kpfpower[port].read()
            if state != 'On':
                msg = f"Final power state mismatch: {state} != On"
                log.error(msg)
                raise KPFError(msg)
        log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## PowerOffCalSource
##-------------------------------------------------------------------------
class PowerOffCalSource():
    '''Powers off one of the cal lamps via the `kpfpower` keyword service.
    
    The mapping between lamp name and power outlet is hard coded for now.
    The only check on this is that the log message will include the name
    of the power outlet which has been powered on as read from the _NAME
    keyword for that outlet.  No automatic checking of the name is currently
    performed, the only check is if a human reads the log line.
    
    The current mapping only handles the following lamps:
    - U_gold
    - U_daily
    - Th_daily
    - Th_gold
    - BrdbandFiber
    '''
    def __init__(self):
        self.ports = {'EtalonFiber': None,
                      'BrdbandFiber': 'OUTLET_CAL2_2',
                      'U_gold': 'OUTLET_CAL2_7',
                      'U_daily': 'OUTLET_CAL2_8',
                      'Th_daily': 'OUTLET_CAL2_6',
                      'Th_gold': 'OUTLET_CAL2_5',
                      'SoCal-CalFib': None,
                      'LFCFiber': None,
                      }


    def pre_condition(self, args):
        pass


    def perform(self, args):
        kpfpower = ktl.cache('kpfpower')
        port = self.ports.get(args.get('lamp', None))
        if port is not None:
            port_name = kpfpower[f"{port}_NAME"].read()
            log.info(f"  Powering off {args.lamp}")
            log.info(f"    Unlocking {port}: {port_name}")
            kpfpower[f"{port}_LOCK"].write('Unlocked')
            log.info(f"    Turning on {port}: {port_name}")
            kpfpower[port].write('Off')
            log.info(f"    Locking {port}: {port_name}")
            kpfpower[f"{port}_LOCK"].write('Locked')


    def post_condition(self, args):
        '''Verifies that the relevant power port is actually off.
        '''
        kpfpower = ktl.cache('kpfpower')
        port = self.ports.get(args.get('lamp', None))
        if port is not None:
            port_name = kpfpower[f"{port}_NAME"].read()
            log.info(f"    Reading {port}: {port_name}")
            state = kpfpower[port].read()
            if state != 'Off':
                msg = f"Final power state mismatch: {state} != Off"
                log.error(msg)
                raise KPFError(msg)
        log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## SetCalSource
##-------------------------------------------------------------------------
class SetCalSource():
    '''
    Selects which source is fed from the octagon in to the cal bench via the
    kpfmot.OCTAGON keyword.
    
    Valid names: Home, EtalonFiber, BrdbandFiber, U_gold, U_daily,
    Th_daily, Th_gold, SoCal-CalFib, LFCFiber
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        target = args.get('OctagonSource', None)
        if target is not None:
            log.info(f"  Setting Cal Source (Octagon) to {target}")
            kpfmot = ktl.cache('kpfmot')
            kpfmot['OCTAGON'].write(target)


    def post_condition(self, args):
        '''Verifies that the final OCTAGON keyword value matches the input.
        '''
        target = args.get('OctagonSource', None)
        kpfmot = ktl.cache('kpfmot')
        final_pos = kpfmot['OCTAGON'].read()
        if final_pos != target:
            msg = f"Final octagon position mismatch: {final_pos} != {target}"
            log.error(msg)
            raise KPFError(msg)
        log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## SetND1
##-------------------------------------------------------------------------
class SetND1():
    '''Set the filter in the ND1 filter wheel (the one at the output of the 
    octagon) via the `kpfmot.ND1POS` keyword.
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        ND1_target = args.get('ND1', None)
        if ND1_target is not None:
            log.info(f"  Setting ND1 to {ND1_target}")
            kpfmot = ktl.cache('kpfmot')
            kpfmot['ND1POS'].write(ND1_target)


    def post_condition(self, args):
        ND1_target = args.get('ND1', None)
        if ND1_target is not None:
            kpfmot = ktl.cache('kpfmot')
            final_pos = kpfmot['ND1POS'].read()
            if final_pos != ND1_target:
                msg = f"Final ND1 position mismatch: {final_pos} != {ND1_target}"
                log.error(msg)
                raise KPFError(msg)
            log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## SetND2
##-------------------------------------------------------------------------
class SetND2():
    '''Set the filter in the ND1 filter wheel (the one at the output of the 
    octagon) via the `kpfmot.ND2POS` keyword.
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        ND2_target = args.get('ND2', None)
        if ND2_target is not None:
            log.info(f"  Setting ND2 to {ND2_target}")
            kpfmot = ktl.cache('kpfmot')
            kpfmot['ND2POS'].write(ND2_target)


    def post_condition(self, args):
        ND2_target = args.get('ND2', None)
        if ND2_target is not None:
            kpfmot = ktl.cache('kpfmot')
            final_pos = kpfmot['ND2POS'].read()
            if final_pos != ND2_target:
                msg = f"Final ND2 position mismatch: {final_pos} != {ND2_target}"
                log.error(msg)
                raise KPFError(msg)
            log.info('    Done')


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)



##-------------------------------------------------------------------------
## SetTriggeredDetectors
##-------------------------------------------------------------------------
class SetTriggeredDetectors():
    '''Selects which cameras will be triggered by setting the
    `kpfexpose.TRIG_TARG` keyword value.
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        detector_list = []
        if args.get('TriggerRed', False) is True:
            detector_list.append('Red')
        if args.get('TriggerGreen', False) is True:
            detector_list.append('Green')
        if args.get('TriggerCaHK', False) is True:
            detector_list.append('Ca_HK')

        detectors_string = ','.join(detector_list)
        log.info(f"  Setting triggered detectors to '{detectors_string}'")
        kpfexpose = ktl.cache('kpfexpose')
        kpfexpose['TRIG_TARG'].write(detectors_string)


    def post_condition(self, args):
        kpfexpose = ktl.cache('kpfexpose')
        detectors = kpfexpose['TRIG_TARG'].read()
        detector_list = detectors.split(',')

        red_status = 'Red' in detector_list
        red_target = args.get('TriggerRed', False)
        if red_target != red_status:
            msg = (f"Final Red detector trigger mismatch: "
                   f"{red_status} != {red_target}")
            log.error(msg)
            raise KPFError(msg)

        green_status = 'Green' in detector_list
        green_target = args.get('TriggerGreen', False)
        if green_target != green_status:
            msg = (f"Final Green detector trigger mismatch: "
                   f"{green_status} != {green_target}")
            log.error(msg)
            raise KPFError(msg)

        CaHK_status = 'Ca_HK' in detector_list
        CaHK_target = args.get('TriggerCaHK', False)
        if CaHK_target != CaHK_status:
            msg = (f"Final Ca HK detector trigger mismatch: "
                   f"{CaHK_status} != {CaHK_target}")
            log.error(msg)
            raise KPFError(msg)

        log.info(f"    Done")


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## SetSourceSelectShutters
##-------------------------------------------------------------------------
class SetSourceSelectShutters():
    '''Opens and closes the source select shutters via the 
    `kpfexpose.SRC_SHUTTERS` keyword.
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        shutter_list = []
        if args.get('SSS_Science', False) is True:
            shutter_list.append('SciSelect')
        if args.get('SSS_Sky', False) is True:
            shutter_list.append('SkySelect')
        if args.get('SSS_SoCalSci', False) is True:
            shutter_list.append('SoCalSci')
        if args.get('SSS_SoCalCal', False) is True:
            shutter_list.append('SoCalCal')
        if args.get('SSS_CalSciSky', False) is True:
            shutter_list.append('Cal_SciSky')
        shutters_string = ','.join(shutter_list)
        log.info(f"  Setting source select shutters to '{shutters_string}'")
        kpfexpose = ktl.cache('kpfexpose')
        kpfexpose['SRC_SHUTTERS'].write(shutters_string)


    def post_condition(self, args):
        kpfexpose = ktl.cache('kpfexpose')
        shutters = kpfexpose['SRC_SHUTTERS'].read()
        shutter_list = shutters.split(',')

        sci_shutter_status = 'SciSelect' in shutter_list
        sci_shutter_target = args.get('SSS_Science', False)
        if sci_shutter_target != sci_shutter_status:
            msg = (f"Final Science select shutter mismatch: "
                   f"{sci_shutter_status} != {sci_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        sky_shutter_status = 'SkySelect' in shutter_list
        sky_shutter_target = args.get('SSS_Sky', False)
        if sky_shutter_target != sky_shutter_status:
            msg = (f"Final Sky select shutter mismatch: "
                   f"{sky_shutter_status} != {sky_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        socalsci_shutter_status = 'SoCalSci' in shutter_list
        socalsci_shutter_target = args.get('SSS_SoCalSci', False)
        if socalsci_shutter_target != socalsci_shutter_status:
            msg = (f"Final SoCalSci select shutter mismatch: "
                   f"{socalsci_shutter_status} != {socalsci_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        socalcal_shutter_status = 'SoCalCal' in shutter_list
        socalcal_shutter_target = args.get('SSS_SoCalCal', False)
        if socalcal_shutter_target != socalcal_shutter_status:
            msg = (f"Final SoCalCal select shutter mismatch: "
                   f"{socalcal_shutter_status} != {socalcal_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        calscisky_shutter_status = 'Cal_SciSky' in shutter_list
        calscisky_shutter_target = args.get('SSS_CalSciSky', False)
        if calscisky_shutter_target != calscisky_shutter_status:
            msg = (f"Final Cal_SciSky select shutter mismatch: "
                   f"{calscisky_shutter_status} != {calscisky_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        log.info(f"    Done")


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## SetTimedShutters
##-------------------------------------------------------------------------
class SetTimedShutters():
    '''Selects which timed shutters will be triggered by setting the
    `kpfexpose.TIMED_SHUTTERS` keyword value.
    '''
    def __init__(self):
        pass


    def pre_condition(self, args):
        pass


    def perform(self, args):
        # Scrambler 2 SimulCal 3 FF_Fiber 4 Ca_HK
        timed_shutters_list = []
        
        if args.get('TS_Scrambler', False) is True:
            timed_shutters_list.append('Scrambler')
        if args.get('TS_SimulCal', False) is True:
            timed_shutters_list.append('SimulCal')
        if args.get('TS_FF_Fiber', False) is True:
            timed_shutters_list.append('FF_Fiber')
        if args.get('TS_CaHK', False) is True:
            timed_shutters_list.append('Ca_HK')
        timed_shutters_string = ','.join(timed_shutters_list)
        log.info(f"  Setting timed shutters to '{timed_shutters_string}'")
        kpfexpose = ktl.cache('kpfexpose')
        kpfexpose['TIMED_SHUTTERS'].write(timed_shutters_string)


    def post_condition(self, args):
        kpfexpose = ktl.cache('kpfexpose')
        shutters = kpfexpose['TIMED_SHUTTERS'].read()
        shutter_list = shutters.split(',')

        Scrambler_shutter_status = 'Scrambler' in shutter_list
        Scrambler_shutter_target = args.get('TS_Scrambler', False)
        if Scrambler_shutter_target != Scrambler_shutter_status:
            msg = (f"Final Scrambler timed shutter mismatch: "
                   f"{Scrambler_shutter_status} != {Scrambler_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        SimulCal_shutter_status = 'SimulCal' in shutter_list
        SimulCal_shutter_target = args.get('TS_SimulCal', False)
        if SimulCal_shutter_target != SimulCal_shutter_status:
            msg = (f"Final SimulCal timed shutter mismatch: "
                   f"{SimulCal_shutter_status} != {SimulCal_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        FF_Fiber_shutter_status = 'FF_Fiber' in shutter_list
        FF_Fiber_shutter_target = args.get('TS_FF_Fiber', False)
        if FF_Fiber_shutter_target != FF_Fiber_shutter_status:
            msg = (f"Final FF_Fiber timed shutter mismatch: "
                   f"{FF_Fiber_shutter_status} != {FF_Fiber_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        Ca_HK_shutter_status = 'Ca_HK' in shutter_list
        CA_HK_shutter_target = args.get('TS_CaHK', False)
        if CA_HK_shutter_target != Ca_HK_shutter_status:
            msg = (f"Final Ca_HK timed shutter mismatch: "
                   f"{Ca_HK_shutter_status} != {CA_HK_shutter_target}")
            log.error(msg)
            raise KPFError(msg)

        log.info(f"    Done")


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## RunCalSequence
##-------------------------------------------------------------------------
class RunCalSequence():
    '''Loops over all input files (args.files). Each file is parsed as YAML
    and the keyword-value pairs in the resulting dictionary control the
    subsequent actions.
    
    The loop is repeated a number of times equal to the args.count value (which
    is the -n argument on the command line).
    
    
    '''
    def __init__(self):
        pass

    def pre_condition(self, args):
        for file in args.files:
            file = Path(file)
            if file.exists() is False:
                msg = f"Input file {args.file} does not exist"
                log.info(msg)
                raise FileNotFoundError(msg)


    def perform(self, args):
        sequences = [yaml.load(open(file)) for file in args.files]
        log.info(f"Read {len(sequences)} sequence files")

        lamps = set([entry['OctagonSource'] for entry in sequences])
        for lamp in lamps:
            # Turn on lamps
            action = PowerOnCalSource()
            action.execute({'lamp': lamp})

        warm_up_time = max([entry['WarmUp'] for entry in sequences])

        log.info(f"Sleeping {warm_up_time:.0f} s for lamps to warm up")
        sleep(warm_up_time)

        for count in range(0,args.count):
            for i,sequence in enumerate(sequences):
                log.info(f"(Repeat {count+1}/{args.count}): Executing sequence "
                         f"{i+1}/{len(sequences)} ({args.files[i]})")

                # Set Cal Source
                action = SetCalSource()
                action.execute(sequence)

                # Set Source Select Shutters
                action = SetSourceSelectShutters()
                action.execute(sequence)

                # Set Timed Shutters
                action = SetTimedShutters()
                action.execute(sequence)

                # Set ND1 Filter Wheel
                action = SetND1()
                action.execute(sequence)

                # Set ND2 Filter Wheel
                action = SetND2()
                action.execute(sequence)

                # Set exposure time
                action = SetExptime()
                action.execute(sequence)

                # Wait for Exposure to be Complete
                action = WaitForReady()
                action.execute(sequence)

                # Set Detector List
                action = SetTriggeredDetectors()
                action.execute(sequence)

                nexp = sequence.get('nExp', 1)
                for j in range(nexp):
                    # Wait for Exposure to be Complete
                    action = WaitForReady()
                    action.execute(sequence)

                    log.info(f"  Starting expoure {j+1}/{nexp}")
                    # Start Exposure
                    action = StartExposure()
                    if args.noexp is False: action.execute(sequence)

                    # Wait for Readout to Begin
                    action = WaitForReadout()
                    if args.noexp is False: action.execute(sequence)


        if args.lampsoff is True:
            for lamp in lamps:
                # Turn off lamps
                action = PowerOffCalSource()
                action.execute({'lamp': lamp})

        # Wait for Exposure to be Complete
        action = WaitForReady()
        action.execute(sequence)


    def post_condition(self, args):
        kpfexpose = ktl.cache('kpfexpose')
        expose = kpfexpose['EXPOSE']
        status = expose.read()
        if status != 'Ready':
            msg = f"Final detector state mismatch: {status} != Ready"
            log.error(msg)
            raise KPFError(msg)


    def execute(self, args):
        self.pre_condition(args)
        self.perform(args)
        self.post_condition(args)


##-------------------------------------------------------------------------
## __main__
##-------------------------------------------------------------------------
if __name__ == '__main__':
    ## create a parser object for understanding command-line arguments
    p = argparse.ArgumentParser(description='''
    ''')
    p.add_argument('files', nargs='*',
                   help="Config files to run")
    ## add flags
    p.add_argument("-n", dest="count", type=int, default=1,
                   help="The number of times to run the set of config files.")
    ## add flags
    p.add_argument("--off", "--lampsoff", dest="lampsoff",
                   default=False, action="store_true",
                   help="Turn lamps off at end of run? (default = False)")
    p.add_argument("--noexp", dest="noexp",
                   default=False, action="store_true",
                   help="Don't trigger exposures (used for testing)")
    args = p.parse_args()

    action = RunCalSequence()
    action.execute(args)
