from __future__ import division # confidence medium

import sys,os,copy
import util
import numpy as np
import pyfits
from pytools import fileutil, teal
import outputimage,wcs_functions,processInput,util
import stwcs
from stwcs import distortion

try:
    import cdriz
except ImportError:
    cdriz = None
    print '\n Coordinate transformation and image resampling library, cdriz, NOT found!'
    print '\n Please check the installation of this package to insure C code was built successfully.'
    raise ImportError

can_parallel = False
num_processors = 1
if 'BETADRIZ_NO_PARALLEL' in os.environ:
    try:
        import multiprocessing
        can_parallel = True
        # sanity check - do we have the hardware?
        num_processors = multiprocessing.cpu_count()
        if num_processors < 2:
            can_parallel = False
    except:
        multiprocessing = None
        print '\nCould not import multiprocessing, will only be able to take advantage of a single CPU core'

__taskname__ = "betadrizzle.adrizzle"
_single_step_num_ = 3
_final_step_num_ = 7


#
#### Interactive interface for running drizzle tasks separately
#

def drizzle(input, outdata, wcsmap=None, editpars=False, configObj=None, **input_dict):

    # Pass along values of input and outdata as members of input_dict
    if input_dict is None:
        input_dict = {}
    input_dict['input'] = input
    input_dict['outdata'] = outdata
    
    # If called from interactive user-interface, configObj will not be
    # defined yet, so get defaults using EPAR/TEAL.
    #
    # Also insure that the input_dict (user-specified values) are folded in
    # with a fully populated configObj instance.
    configObj = util.getDefaultConfigObj(__taskname__,configObj,input_dict,loadOnly=(not editpars))
    if configObj is None:
        return

    if not editpars:
        run(configObj,wcsmap=wcsmap)
#
####  User level interface to run drizzle tasks from TEAL
#
def run(configObj, wcsmap=None):
    """ Interface for running 'wdrizzle' from TEAL or Python command-line.

    This code performs all file I/O to set up the use of the drizzle code for
    a single exposure to replicate the functionality of the original 'wdrizzle'.
    """

    # Insure all output filenames specified have .fits extensions
    if configObj['outdata'][-5:] != '.fits': configObj['outdata'] += '.fits'
    if not util.is_blank(configObj['outweight']) and configObj['outweight'][-5:] != '.fits': configObj['outweight'] += '.fits'
    if not util.is_blank(configObj['outcontext']) and configObj['outcontext'][-5:] != '.fits': configObj['outcontext'] += '.fits'

    # Keep track of any files we need to open
    in_sci_handle = None
    in_wht_handle = None
    out_sci_handle = None
    out_wht_handle = None
    out_con_handle = None

    _wcskey = configObj['wcskey']
    if util.is_blank(_wcskey):
        _wcskey = ' '

    scale_pars = configObj['Data Scaling Parameters']
    user_wcs_pars = configObj['User WCS Parameters']

    # Open the SCI (and WHT?) image
    # read file to get science array
    insci = get_data(configObj['input'])
    expin = fileutil.getKeyword(configObj['input'],scale_pars['expkey'])
    in_sci_phdr = pyfits.getheader(fileutil.parseFilename(configObj['input'])[0])

    # we need to read in the input WCS
    input_wcs = stwcs.wcsutil.HSTWCS(configObj['input'],wcskey=_wcskey)

    if not util.is_blank(configObj['inweight']):
        inwht = get_data(configObj['inweight']).astype(np.float32)
    else:
        # Generate a default weight map of all good pixels
        inwht = np.ones(insci.shape,dtype=insci.dtype)

    output_exists = False
    outname = fileutil.osfn(fileutil.parseFilename(configObj['outdata'])[0])
    if os.path.exists(outname):
        output_exists = True
    # Output was specified as a filename, so open it in 'update' mode
    outsci = get_data(configObj['outdata'])

    if output_exists:
        # we also need to read in the output WCS from pre-existing output
        output_wcs = stwcs.wcsutil.HSTWCS(configObj['outdata'])

        out_sci_hdr = pyfits.getheader(outname)
        outexptime = out_sci_hdr['DRIZEXPT']
        if out_sci_hdr.has_key('ndrizim'):
            uniqid = out_sci_hdr['ndrizim']+1
        else:
            uniqid = 1
        
    else: # otherwise, define the output WCS either from user pars or refimage
        if util.is_blank(configObj['User WCS Parameters']['refimage']):
            # Define a WCS based on user provided WCS values
            # NOTE:
            #   All parameters must be specified, not just one or a few
            if not util.is_blank(user_wcs_pars['outscale']):
                output_wcs = wcs_functions.build_hstwcs(
                    user_wcs_pars['raref'], user_wcs_pars['decref'],
                    user_wcs_pars['xrefpix'], user_wcs_pars['yrefpix'],
                    user_wcs_pars['outnx'], user_wcs_pars['outny'],
                    user_wcs_pars['outscale'], user_wcs_pars['orient'] )
            else:
                # Define default WCS based on input image
                applydist = True
                if input_wcs.sip is None:
                    applydist = False
                output_wcs = stwcs.distortion.utils.output_wcs([input_wcs],undistort=applydist)
        else:
            # Define the output WCS based on a user specified reference image WCS
            output_wcs = stwcs.wcsutil.HSTWCS(configObj['User WCS Parameters']['refimage'])

        # Initialize values used for combining results
        outexptime = 0.0
        uniqid = 1

    # Set up the output data array and insure that the units for that array is 'cps'
    if outsci is None:
        # Define a default blank array based on definition of output_wcs
        outsci = np.zeros((output_wcs.naxis2,output_wcs.naxis1),dtype=np.float32)
    else:
        # Convert array to units of 'cps', if needed
        if outexptime != 0.0:
            np.divide(outsci, outexptime, outsci)
        outsci = outsci.astype(np.float32)

    # Now update output exposure time for additional input file
    outexptime += expin

    outwht = None
    if not util.is_blank(configObj['outweight']):
        outwht = get_data(configObj['outweight'])

    if outwht is None:
        outwht = np.zeros((output_wcs.naxis2,output_wcs.naxis1),dtype=np.float32)
    else:
        outwht = outwht.astype(np.float32)
        
    outcon = None
    keep_con = False    
    
    if not util.is_blank(configObj['outcontext']):
        outcon = get_data(configObj['outcontext'])
        keep_con = True
        if outcon is None:
            outcon = np.zeros((1,output_wcs.naxis2,output_wcs.naxis1),dtype=np.int32)
        else:
            outcon = outcon.astype(np.int32)
    # Interpret wt_scl parameter
    if configObj['wt_scl'] == 'exptime':
        wt_scl = expin
    elif configObj['wt_scl'] == 'expsq':
        wt_scl = expin*expin
    else:
        wt_scl = float(configObj['wt_scl'])

    # Interpret coeffs parameter to determine whether to apply coeffs or not
    undistort = True
    if not configObj['coeffs'] or input_wcs.sip is None:
        undistort = False

    # Perform actual drizzling now...
    _vers = do_driz(insci, input_wcs, inwht,
            output_wcs, outsci, outwht, outcon,
            expin, scale_pars['in_units'],
            wt_scl, undistort=undistort ,uniqid=uniqid,
            pixfrac=configObj['pixfrac'], kernel=configObj['kernel'],
            fillval=scale_pars['fillval'], stepsize=configObj['stepsize'],
            wcsmap=None)

    out_sci_handle,outextn = create_output(configObj['outdata'])
    if not output_exists:
        # Also, define default header based on input image Primary header
        out_sci_handle[outextn].header = in_sci_phdr.copy()

    # Update header of output image with exptime used to scale the output data
    # if out_units is not counts, this will simply be a value of 1.0
    # the keyword 'exptime' will always contain the total exposure time
    # of all input image regardless of the output units
    out_sci_handle[outextn].header.update('EXPTIME', outexptime)

    # create CTYPE strings
    ctype1 = input_wcs.wcs.ctype[0]
    ctype2 = input_wcs.wcs.ctype[1]
    if ctype1.find('-SIP'): ctype1 = ctype1.replace('-SIP','')
    if ctype2.find('-SIP'): ctype2 = ctype2.replace('-SIP','')
    
    # Update header with WCS keywords
    out_sci_handle[outextn].header.update('ORIENTAT',output_wcs.orientat)
    out_sci_handle[outextn].header.update('CD1_1',output_wcs.wcs.cd[0][0])
    out_sci_handle[outextn].header.update('CD1_2',output_wcs.wcs.cd[0][1])
    out_sci_handle[outextn].header.update('CD2_1',output_wcs.wcs.cd[1][0])
    out_sci_handle[outextn].header.update('CD2_2',output_wcs.wcs.cd[1][1])
    out_sci_handle[outextn].header.update('CRVAL1',output_wcs.wcs.crval[0])
    out_sci_handle[outextn].header.update('CRVAL2',output_wcs.wcs.crval[1])
    out_sci_handle[outextn].header.update('CRPIX1',output_wcs.wcs.crpix[0])
    out_sci_handle[outextn].header.update('CRPIX2',output_wcs.wcs.crpix[1])
    out_sci_handle[outextn].header.update('CTYPE1',ctype1)
    out_sci_handle[outextn].header.update('CTYPE2',ctype2)
    out_sci_handle[outextn].header.update('VAFACTOR',1.0)


    if scale_pars['out_units'] == 'counts':
        np.multiply(outsci, outexptime, outsci)
        out_sci_handle[outextn].header.update('DRIZEXPT', outexptime)

    else:
        out_sci_handle[outextn].header.update('DRIZEXPT', 1.0)

    # Update header keyword NDRIZIM to keep track of how many images have
    # been combined in this product so far
    out_sci_handle[outextn].header.update('NDRIZIM', uniqid)

    #define keywords to be written out to product header
    drizdict = outputimage.DRIZ_KEYWORDS.copy()

    # Update drizdict with current values
    drizdict['VER']['value'] = _vers[:44]
    drizdict['DATA']['value'] = configObj['input'][:64]
    drizdict['DEXP']['value'] = expin
    drizdict['OUDA']['value'] = configObj['outdata'][:64]
    drizdict['OUWE']['value'] = configObj['outweight'][:64]
    drizdict['OUCO']['value'] = configObj['outcontext'][:64]
    drizdict['MASK']['value'] = configObj['inweight'][:64]
    drizdict['WTSC']['value'] = wt_scl
    drizdict['KERN']['value'] = configObj['kernel']
    drizdict['PIXF']['value'] = configObj['pixfrac']
    drizdict['OUUN']['value'] = scale_pars['out_units']
    drizdict['FVAL']['value'] = scale_pars['fillval']
    drizdict['WKEY']['value'] = configObj['wcskey']
    outputimage.writeDrizKeywords(out_sci_handle[outextn].header,uniqid,drizdict)

    # add output array to output file
    out_sci_handle[outextn].data = outsci
    out_sci_handle.close()

    if not util.is_blank(configObj['outweight']):
        out_wht_handle,outwhtext = create_output(configObj['outweight'])
        out_wht_handle[outwhtext].header = out_sci_handle[outextn].header.copy()
        out_wht_handle[outwhtext].data = outwht
        out_wht_handle.close()

    if keep_con:
        out_con_handle,outconext = create_output(configObj['outcontext'])
        out_con_handle[outconext].data = outcon
        out_con_handle.close()


def help():
    print getHelpAsString()

def getHelpAsString():
    """
    return useful help from a file in the script directory called module.help
    """
    helpString = teal.getHelpFileAsString(__taskname__,__file__)

    return helpString



#
# Betadrizzle based interfaces: relying on imageObject instances and betadrizzle internals
#
#
#### Top-level interface from inside MultiDrizzle
#
def drizSeparate(imageObjectList,output_wcs,configObj,wcsmap=None,procSteps=None):
    if procSteps is not None:
        procSteps.addStep('Separate Drizzle')

    # ConfigObj needs to be parsed specifically for driz_separate set of parameters
    single_step = util.getSectionName(configObj,_single_step_num_)
    # This can be called directly from MultiDrizle, so only execute if
    # switch has been turned on (no guarantee MD will check before calling).
    if configObj[single_step]['driz_separate']:
        paramDict = buildDrizParamDict(configObj)
        paramDict['crbit'] = None
        paramDict['proc_unit'] = 'electrons'
        paramDict['wht_type'] = None
        # Force 'build' to always be False, so that this step always generates
        # simple FITS files as output for compatibility with 'createMedian'
        paramDict['build'] = False

        print "\nUSER INPUT PARAMETERS for Separate Drizzle Step:"
        util.printParams(paramDict)

        # override configObj[build] value with the value of the build parameter
        # this is necessary in order for MultiDrizzle to always have build=False
        # for single-drizzle step when called from the top-level.
        run_driz(imageObjectList, output_wcs.single_wcs, paramDict, single=True,
                build=False, wcsmap=wcsmap)
    else:
        print 'Single drizzle step not performed.'

    if procSteps is not None:
        procSteps.endStep('Separate Drizzle')


def drizFinal(imageObjectList, output_wcs, configObj,build=None,wcsmap=None,procSteps=None):
    if procSteps is not None:
        procSteps.addStep('Final Drizzle')
    # ConfigObj needs to be parsed specifically for driz_final set of parameters
    final_step = util.getSectionName(configObj,_final_step_num_)
    # This can be called directly from MultiDrizle, so only execute if
    # switch has been turned on (no guarantee MD will check before calling).
    if configObj[final_step]['driz_combine']:
        paramDict = buildDrizParamDict(configObj,single=False)
        paramDict['crbit'] = configObj['crbit']
        paramDict['proc_unit'] = configObj['proc_unit']
        paramDict['wht_type'] = configObj[final_step]['final_wht_type']

        # override configObj[build] value with the value of the build parameter
        # this is necessary in order for MultiDrizzle to always have build=False
        # for single-drizzle step when called from the top-level.
        if build is None:
            build = paramDict['build']

        print "\nUSER INPUT PARAMETERS for Final Drizzle Step:"
        util.printParams(paramDict)

        run_driz(imageObjectList, output_wcs.final_wcs, paramDict, single=False,
                build=build, wcsmap=wcsmap)
    else:
        print 'Final drizzle step not performed.'

    if procSteps is not None:
        procSteps.endStep('Final Drizzle')

# Run 'drizzle' here...
#

def mergeDQarray(maskname,dqarr):
    """ Merge static or CR mask with mask created from DQ array on-the-fly here.
    """
    if maskname is not None and os.path.exists(maskname):
        mask = fileutil.openImage(maskname)
        maskarr = mask[0].data
        np.bitwise_and(dqarr,maskarr,dqarr)
        mask.close()

def updateInputDQArray(dqfile,dq_extn,chip, crmaskname,cr_bits_value):
    if not os.path.exists(crmaskname):
        print 'WARNING: No CR mask file found! Input DQ array not updated.'
        return
    if cr_bits_value == None:
        print 'WARNING: Input DQ array not updated!'
        return
    crmask = fileutil.openImage(crmaskname)

    if os.path.exists(dqfile):
        fullext=dqfile+"["+dq_extn+str(chip)+"]"
        infile = fileutil.openImage(fullext,mode='update')
        __bitarray = np.logical_not(crmask[0].data).astype(np.int16) * cr_bits_value
        np.bitwise_or(infile[dq_extn,chip].data,__bitarray,infile[dq_extn,chip].data)
        infile.close()
        crmask.close()

def buildDrizParamDict(configObj,single=True):
    chip_pars = ['units','wt_scl','pixfrac','kernel','fillval','bits']
    # Initialize paramDict with global parameter(s)
    paramDict = {'build':configObj['build'],'stepsize':configObj['stepsize'],
                'coeffs':configObj['coeffs'],'wcskey':configObj['wcskey']}

    # build appro
    if single:
        driz_prefix = 'driz_sep_'
        stepnum = 3
    else:
        driz_prefix = 'final_'
        stepnum = 7
    section_name = util.getSectionName(configObj,stepnum)
    # Copy values from configObj for the appropriate step to paramDict
    for par in chip_pars:
        if par == 'units':
            if single:
                # Hard-code single-drizzle to always returns 'cps'
                paramDict[par] = 'cps'
            else:
                paramDict[par] = configObj[section_name][driz_prefix+par]
        else:
            paramDict[par] = configObj[section_name][driz_prefix+par]
    return paramDict

def _setDefaults(configObj={}):
    """set up the default parameters to run drizzle
        build,single,units,wt_scl,pixfrac,kernel,fillval,
        rot,scale,xsh,ysh,blotnx,blotny,outnx,outny,data

        Used exclusively for unit-testing, if any are defined.
    """

    paramDict={"build":True,
              "single":True,
              "stepsize":10,
              "in_units":"cps",
              "wt_scl":1.,
              "pixfrac":1.,
              "kernel":"square",
              "fillval":999.,
              "rot":0.,
              "scale":1.,
              "xsh":0.,
              "ysh":0.,
              "blotnx":2048,
              "blotny":2048,
              "outnx":4096,
              "outny":4096,
              "data":None,
              "driz_separate":True,
              "driz_combine":False}

    if(len(configObj) !=0):
        for key in configObj.keys():
            paramDict[key]=configObj[key]

    return paramDict

def run_driz(imageObjectList,output_wcs,paramDict,single,build,wcsmap=None):
    """Perform drizzle operation on input to create output.
     The input parameters originally was a list
     of dictionaries, one for each input, that matches the
     primary parameters for an IRAF drizzle task.

     This method would then loop over all the entries in the
     list and run 'drizzle' for each entry.

    Parameters required for input in paramDict:
        build,single,units,wt_scl,pixfrac,kernel,fillval,
        rot,scale,xsh,ysh,blotnx,blotny,outnx,outny,data
    """
    # Insure that input imageObject is a list
    if not isinstance(imageObjectList, list):
        imageObjectList = [imageObjectList]

    #
    # Setup the versions info dictionary for output to PRIMARY header
    # The keys will be used as the name reported in the header, as-is
    #
    _versions = {'PyDrizzle':util.__version__,'PyFITS':util.__pyfits_version__,'Numpy':util.__numpy_version__}

    # Set sub-sampling rate for drizzling
    #stepsize = 2.0
    print '  **Using sub-sampling value of ',paramDict['stepsize'],' for kernel ',paramDict['kernel']

    outwcs = copy.deepcopy(output_wcs)

    # Check for existance of output file.
    if single == False and build == True and fileutil.findFile(imageObjectList[0].outputNames['outFinal']):
        print 'Removing previous output product...'
        os.remove(imageObjectList[0].outputNames['outFinal'])

    # print out parameters being used for drizzling
    print "Running Drizzle to create output frame with WCS of: "
    output_wcs.printwcs()
    print '\n'

    # Set parameters for each input and run drizzle on it here.
    #
    # Perform drizzling...
    #

    numctx = 0
    for img in imageObjectList:
        numctx += img._nmembers
    _numctx = {'all':numctx}

    #            if single:
    # Determine how many chips make up each single image
    for img in imageObjectList:
        for chip in img.returnAllChips(extname=img.scienceExt):
            plsingle = chip.outputNames['outSingle']
            if _numctx.has_key(plsingle): _numctx[plsingle] += 1
            else: _numctx[plsingle] = 1
    #
    # A image buffer needs to be setup for converting the input
    # arrays (sci and wht) from FITS format to native format
    # with respect to byteorder and byteswapping.
    # This buffer should be reused for each input.
    #
    _outsci = _outwht = _outctx = None
    if not single or not can_parallel:
        _outsci=np.zeros((output_wcs.naxis2,output_wcs.naxis1),dtype=np.float32)
        _outwht=np.zeros((output_wcs.naxis2,output_wcs.naxis1),dtype=np.float32)

    # Compute how many planes will be needed for the context image.
    _nplanes = int((_numctx['all']-1) / 32) + 1
    # For single drizzling or when context is turned off,
    # minimize to 1 plane only...
    if single or imageObjectList[0][1].outputNames['outContext'] in [None,'',' ']:
        _nplanes = 1

    # Always initialize context images to a 3-D array
    # and only pass the appropriate plane to drizzle as needed
    if not single or not can_parallel:
        _outctx = np.zeros((_nplanes,output_wcs.naxis2,output_wcs.naxis1),dtype=np.int32)

    # Keep track of how many chips have been processed
    # For single case, this will determine when to close
    # one product and open the next.
    _numchips = 0
    _hdrlist = []
    # Remember the name of the 1st image that goes into this particular product
    # Insure that the header reports the proper values for the start of the
    # exposure time used to make this; in particular, TIME-OBS and DATE-OBS.
    template = None

    subprocs = []

    for img in imageObjectList:
        for chip in img.returnAllChips(extname=img.scienceExt):
            # set template - the name of the 1st image
            if _numchips == 0:
                template = chip.outputNames['data']

            # determine how many inputs should go into this product
            num_in_prod = _numctx['all']
            if single:
                num_in_prod = _numctx[chip.outputNames['outSingle']]

            # See if we will be writing out data
            doWrite = _numchips+1 == num_in_prod

            # run_driz_chip
            if single and can_parallel:
                p = multiprocessing.Process(target=run_driz_chip,
                        args=(img,chip,output_wcs,outwcs,template,paramDict,
                        single, doWrite,build,_versions,_numctx,_nplanes,
                        _numchips, None,None,None,[],wcsmap))
                subprocs.append(p)
                p.start() # ! just first cut - we will use a pool for this
            else:
                run_driz_chip(img,chip,output_wcs,outwcs,template,paramDict,
                    single, doWrite,build,_versions,_numctx,_nplanes,_numchips,
                    _outsci,_outwht,_outctx,_hdrlist,wcsmap)

            # Increment/reset chip counter
            if doWrite:
                _numchips = 0
            else:
                _numchips += 1

    # do the join if we spawned tasks
    if len(subprocs) > 0:
        for p in subprocs:
            p.join()

    del _outsci,_outwht,_outctx, _hdrlist
    # end of loop over each chip


#
# Still to check:
#    - why have both output_wcs and outwcs?

def run_driz_chip(img,chip,output_wcs,outwcs,template,paramDict,single,
                  doWrite,build,_versions,_numctx,_nplanes,_numchips,
                  _outsci,_outwht,_outctx,_hdrlist,wcsmap):
    """ Perform drizzle operation on a single image/chip.
    This is separated out from run_driz() so as to collect
    the entirety of the code which is inside the loop over
    images/chips.  See the calling code for more documentation.
    """
    # Check for unintialized inputs
    if _outsci is None:
        _outsci=np.zeros((output_wcs.naxis2,output_wcs.naxis1),dtype=np.float32)
    if _outwht is None:
        _outwht=np.zeros((output_wcs.naxis2,output_wcs.naxis1),dtype=np.float32)
    if _outctx is None:
       _outctx = np.zeros((_nplanes,output_wcs.naxis2,output_wcs.naxis1),dtype=np.int32)

    # Look for sky-subtracted product.
    if os.path.exists(chip.outputNames['outSky']):
        chipextn = '['+chip.header['extname']+','+str(chip.header['extver'])+']'
        _expname = chip.outputNames['outSky']+chipextn
    else:
        # If sky-subtracted product does not exist, use regular input
        _expname = chip.outputNames['data']
    print '-Drizzle input: ',_expname

    # Open the SCI image
    _handle = fileutil.openImage(_expname,mode='readonly',memmap=0)
    _sciext = _handle[chip.header['extname'],chip.header['extver']]

    # Set additional parameters needed by 'drizzle'
    _in_units = chip.in_units.lower()
    if _in_units == 'cps':
        _expin = 1.0
    else:
        _expin = chip._exptime

    # compute the undistorted 'natural' plate scale for this chip
    undistort = True
    if not paramDict['coeffs']:
        chip.wcs.sip = None
        chip.wcs.cpdis1 = None
        chip.wcs.cpdis2 = None
        chip.wcs.det2im = None
        undistort=False

    ####
    #
    # Put the units keyword handling in the imageObject class
    #
    ####
    # Determine output value of BUNITS
    # and make sure it is not specified as 'ergs/cm...'
    _bunit = chip._bunit

    _bindx = _bunit.find('/')

    if paramDict['units'] == 'cps':
        # If BUNIT value does not specify count rate already...
        if _bindx < 1:
            # ... append '/SEC' to value
            _bunit += '/S'
        else:
            # reset _bunit here to None so it does not
            #    overwrite what is already in header
            _bunit = None
    else:
        if _bindx > 0:
            # remove '/S'
            _bunit = _bunit[:_bindx]
        else:
            # reset _bunit here to None so it does not
            #    overwrite what is already in header
            _bunit = None

    _uniqid = _numchips + 1
    if _nplanes == 1:
        # We need to reset what gets passed to TDRIZ
        # when only 1 context image plane gets generated
        # to prevent overflow problems with trying to access
        # planes that weren't created for large numbers of inputs.
        _uniqid = ((_uniqid-1) % 32) + 1

    # Select which mask needs to be read in for drizzling
    ####
    #
    # Actually need to generate mask file here 'on-demand'
    # and combine it with the static_mask for single_drizzle case...
    #
    ####
    # Build basic DQMask from DQ array and bits value
    dqarr = img.buildMask(chip._chip,bits=paramDict['bits'])

    # Merge appropriate additional mask(s) with DQ mask
    if single:
        mergeDQarray(chip.outputNames['staticMask'],dqarr)
    else:
        mergeDQarray(chip.outputNames['staticMask'],dqarr)
        mergeDQarray(chip.outputNames['crmaskImage'],dqarr)
        updateInputDQArray(chip.dqfile,chip.dq_extn,chip._chip,
                           chip.outputNames['crmaskImage'],paramDict['crbit'])

    img.set_wtscl(chip._chip,paramDict['wt_scl'])

    wcslin = distortion.utils.output_wcs([chip.wcs],undistort=undistort)
    pix_ratio = outwcs.pscale/wcslin.pscale

    # Convert mask to a datatype expected by 'tdriz'
    # Also, base weight mask on ERR or IVM file as requested by user
    wht_type = paramDict['wht_type']
    if wht_type == 'ERR':
        _inwht = img.buildERRmask(chip._chip,dqarr,pix_ratio)
    elif wht_type == 'IVM':
        _inwht = img.buildIVMmask(chip._chip,dqarr,pix_ratio)
    else: # wht_type == 'EXP'
        _inwht = dqarr.astype(np.float32)

    # New interface to performing the drizzle operation on a single chip/image
    _vers = do_driz(_sciext.data, chip.wcs, _inwht, outwcs, _outsci, _outwht, _outctx,
                _expin, _in_units, chip._wtscl,
                undistort=undistort, uniqid=_uniqid,
                pixfrac=paramDict['pixfrac'], kernel=paramDict['kernel'],
                fillval=paramDict['fillval'], stepsize=paramDict['stepsize'],
                wcsmap=wcsmap)

    # Set up information for generating output FITS image
    #### Check to see what names need to be included here for use in _hdrlist
    chip.outputNames['driz_version'] = _vers
    chip.outputNames['driz_wcskey'] = paramDict['wcskey']
    outputvals = chip.outputNames.copy()
    # Update entries for names/values based on final output
    outputvals.update(img.outputValues)
    outputvals.update(img.outputNames)
    _hdrlist.append(outputvals)

    if doWrite:
        ###########################
        #
        #   IMPLEMENTATION REQUIREMENT:
        #
        # Need to implement scaling of the output image
        # from 'cps' to 'counts' in the case where 'units'
        # was set to 'counts'... 21-Mar-2005
        #
        ###########################

        #determine what exposure time needs to be used
        # to rescale the product.
        if single:
            _expscale = chip._exptime
        else:
            _expscale = img.outputValues['texptime']

        # Convert output data from electrons/sec to counts/sec as specified
        native_units = img.native_units
        if paramDict['proc_unit'].lower() == 'native' and native_units.lower()[:6] == 'counts':
            np.divide(_outsci, chip._gain, _outsci)
            _bunit = native_units.lower()
            if paramDict['units'] == 'counts':
                indx = _bunit.find('/')
                if indx > 0: _bunit = _bunit[:indx]

        # record IDCSCALE for output to product header
        paramDict['idcscale'] = chip.wcs.idcscale
        #If output units were set to 'counts', rescale the array in-place
        if paramDict['units'] == 'counts':
            np.multiply(_outsci, _expscale, _outsci)

        #
        # Write output arrays to FITS file(s) and reset chip counter
        #
        _outimg = outputimage.OutputImage(_hdrlist, paramDict, build=build,
                                          wcs=output_wcs, single=single)
        _outimg.set_bunit(_bunit)
        _outimg.set_units(paramDict['units'])

        _outimg.writeFITS(template,_outsci,_outwht,ctxarr=_outctx,versions=_versions)
        del _outimg
        #
        # Reset for next output image...
        #
        np.multiply(_outsci,0.,_outsci)
        np.multiply(_outwht,0.,_outwht)
        np.multiply(_outctx,0,_outctx)
        # this was "_hdrlist=[]", but we need to preserve the var ptr itself
        while len(_hdrlist)>0: _hdrlist.pop()


def do_driz(insci, input_wcs, inwht,
            output_wcs, outsci, outwht, outcon,
            expin, in_units, wt_scl,
            undistort=True,uniqid=1, pixfrac=1.0, kernel='square',
            fillval="INDEF", stepsize=10,wcsmap=None):
    """ Core routine for performing 'drizzle' operation on a single input image
        All input values will be Python objects such as ndarrays, instead of filenames
        File handling (input and output) will be performed by calling routine.
    """
    # Insure that the fillval parameter gets properly interpreted for use with tdriz
    if util.is_blank(fillval):
        fillval = 'INDEF'
    else:
        fillval = str(fillval)

    if in_units == 'cps':
        expscale = 1.0
    else:
        expscale = expin

    # Compute what plane of the context image this input would
    # correspond to:
    _planeid = int((uniqid-1) /32)
    # Compute how many planes will be needed for the context image.
    _nplanes = _planeid + 1

    if outcon is not None and (outcon.ndim < 3 or (outcon.ndim == 3 and outcon.shape[0] < _nplanes)):
        # convert context image to 3-D array and pass along correct plane for drizzling
        if outcon.ndim == 3:
            nplanes = outcon.shape[0]+1
        else:
            nplanes = 1
        # We need to expand the context image here to accomodate the addition of
        # this new image
        newcon = np.zeros((nplanes,output_wcs.naxis2,output_wcs.naxis1),dtype=np.int32)
        # now copy original outcon arrays into new array
        if outcon.ndim == 3:
            for n in range(outcon.shape[0]):
                newcon[n] = outcon[n].copy()
        else:
            newcon[0] = outcon.copy()
    else:
        if outcon is None:
            outcon = np.zeros((1,output_wcs.naxis2,output_wcs.naxis1),dtype=np.int32)
            _planeid = 0
        newcon = outcon

    # At this point, newcon will always be a 3-D array, so only pass in
    # correct plane to drizzle code
    outctx = newcon[_planeid]

    # turn off use of coefficients if undistort is False (coeffs == False)
    if not undistort:
        input_wcs.sip = None
        input_wcs.cpdis1 = None
        input_wcs.cpdis2 = None
        input_wcs.det2im = None

    wcslin = distortion.utils.output_wcs([input_wcs],undistort=undistort)
    pix_ratio = output_wcs.pscale/wcslin.pscale

    if wcsmap is None and cdriz is not None:
        print 'Using WCSLIB-based coordinate transformation...'
        print 'stepsize = ',stepsize
        mapping = cdriz.DefaultWCSMapping(input_wcs,output_wcs,int(input_wcs.naxis1),int(input_wcs.naxis2),stepsize)
    else:
        #
        ##Using the Python class for the WCS-based transformation
        #
        # Use user provided mapping function
        print 'Using coordinate transformation defined by user...'
        if wcsmap is None:
            wcsmap = wcs_functions.WCSMap
        wmap = wcsmap(input_wcs,output_wcs)
        mapping = wmap.forward

    _shift_fr = 'output'
    _shift_un = 'output'
    ystart = 0
    nmiss = 0
    nskip = 0
    #
    # This call to 'cdriz.tdriz' uses the new C syntax
    #
    _dny = insci.shape[0]
    # Call 'drizzle' to perform image combination
    if (insci.dtype > np.float32):
        #WARNING: Input array recast as a float32 array
        insci = insci.astype(np.float32)
        
    _vers,nmiss,nskip = cdriz.tdriz(insci, inwht, outsci, outwht,
        outctx, uniqid, ystart, 1, 1, _dny,
        pix_ratio, 1.0, 1.0, 'center', pixfrac,
        kernel, in_units, expscale, wt_scl,
        fillval, nmiss, nskip, 1, mapping)

    if nmiss > 0:
        print '! Warning, ',nmiss,' points were outside the output image.'
    if nskip > 0:
        print '! Note, ',nskip,' input lines were skipped completely.'

    return _vers

def get_data(filename):
    fileroot,extn = fileutil.parseFilename(filename)
    extname = fileutil.parseExtn(extn)
    if extname[0] == '': extname = "PRIMARY"
    if os.path.exists(fileroot):
        handle = fileutil.openImage(filename)
        data = handle[extname].data
        handle.close()
    else: 
        data = None
    return data

def create_output(filename):
    fileroot,extn = fileutil.parseFilename(filename)
    extname = fileutil.parseExtn(extn)
    if extname[0] == '': extname = "PRIMARY"

    if not os.path.exists(fileroot):
        # We need to create the new file
        pimg = pyfits.HDUList()
        phdu = pyfits.PrimaryHDU()
        phdu.header.update('NDRIZIM',1)
        pimg.append(phdu)
        if extn is not None:
            # Create a MEF file with the specified extname
            ehdu = pyfits.ImageHDU(data=arr)
            ehdu.header.update('EXTNAME',extname[0])
            ehdu.header.update('EXTVER',extname[1])
            pimg.append(ehdu)
        print 'Creating new output file: ',fileroot
        pimg.writeto(fileroot)
        del pimg
    else:
        print 'Updating existing output file: ',fileroot
    
    handle = pyfits.open(fileroot,mode='update')

    return handle,extname
