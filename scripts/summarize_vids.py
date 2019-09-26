from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import ffmpeg
import numpy as np
import os
import stat
import sys

from cv2 import imwrite
from os.path import join,relpath,splitext
from shutil import rmtree
from tempfile import TemporaryDirectory
from campvideo.video import Video

# function for computing total number of frames using ffprobe
def num_frames(fpath):
    # probe file
    probe = ffmpeg.probe(fpath)
    # select video stream
    stream = next((stream for stream in probe['streams'] 
                   if stream['codec_type'] == 'video'), None)
    return int(stream['nb_frames']) if stream is not None else None

# command line argument parser
def parse_arguments(argv):
    parser = argparse.ArgumentParser()  
    parser.add_argument('vid_dir',type=str,help='Directory of .mp4 videos')
    parser.add_argument('-l1',default=1,type=float,
                        help='Penalty for representativeness')
    parser.add_argument('-l2',default=5,type=float,
                        help='Penalty for summary length')
    parser.add_argument('-dsf',default=1,type=int,
                        help='Downsampling factor')
    parser.add_argument('-wf','--write-frames',action='store_true',default=False,
                        help='Flag for writing keyframes to .png')

    return parser.parse_args(argv)

# script for summarizing a collection of videos
def main(args):
    # video directory and video paths
    vid_dir = args.vid_dir
    l1,l2 = args.l1, args.l2
    dsf = args.dsf
    wf = args.wf
    
    # list of filepaths
    fpaths = [join(root,name) for root,dirs,files in os.walk(vid_dir)
                                  for name in files 
                                      if name.endswith(('.mp4','.wmv'))]
    n = len(fpaths)
                                         
    # output directory for summary (mimics folder structure of input)
    summ_dir = vid_dir + '_summaries'
    # delete directory if it exists
    if os.path.exists(summ_dir):
        os.chmod(summ_dir, stat.S_IWUSR) # grant all privileges
        rmtree(summ_dir,ignore_errors=True)
    
    os.mkdir(summ_dir)
    
    with TemporaryDirectory() as temp:
        for i,fpath in enumerate(fpaths):
            print('Processing video {0} of {1}... '.format(i+1,n),end='',flush=True)
            
            # resize video to 320 x 240
            rfpath = join(temp,'resized.mp4')
            cmd = ffmpeg.input(fpath,
                       ).output(rfpath,vf='scale=320:240',loglevel=16
                       ).overwrite_output()
            cmd.run()
            
            # instantiate video stream object for original video
            v_orig = Video(fpath)
            
            # compute keyframe indices
            v_res = Video(rfpath)
            kf_ind = v_res.kf_adaptive(rfpath,l1=l1,l2=l2,dsf=dsf)
            
            # rescale kf_ind due to FPS differences between original and resized video
            kf_ind = (v_orig.frame_count * kf_ind) // v_res.frame_count
            
            # output directory for summary
            out_dir = join(summ_dir,relpath(splitext(fpath)[0],vid_dir))
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
            
            # save keyframes indices
            kf_file = join(out_dir,'keyframes.txt')
            with open(kf_file,'w') as fn:
                for i,kf in enumerate(v_orig.frames(kf_ind)):
                    # reject monochramatic frames (determined by intensity variance)
                    if np.average(kf,axis=2,weights=[0.114,0.587,0.299]).std() >= 10:
                        fn.write('{0},'.format(kf_ind[i]))
                        # save keyframe
                        if wf:
                            fname = join(out_dir,'frame_{0:04d}.png'.format(kf_ind[i]))
                            imwrite(fname,kf)
            
            # video summarized
            print('Done!')
        
if __name__ == '__main__':
    main(parse_arguments(sys.argv[1:]))