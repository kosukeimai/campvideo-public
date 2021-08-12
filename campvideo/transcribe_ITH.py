import argparse
import os
import pandas as pd
import string

from campvideo import Video
from os.path import basename,exists,join,sep,splitext
from pkg_resources import get_distribution
from timeit import default_timer

STATES = {"AL":"Alabama", "AK":"Alaska","AR":"Arkansas","AZ":"Arizona","CA":"California",
          "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida",
          "GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana",
          "IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine",
          "MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota",
          "MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska",
          "NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico",
          "NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio",
          "OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island",
          "SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas",
          "UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
          "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming","US":"United States"}

ELECTS = {'sen':'Senate','hou':'House','gov':'Gubernatorial','pre':'Presidential'}

# path to file containing candidate names for elections used in paper
NAMES = join(get_distribution('campvideo').module_path,'campvideo','data','names.csv')

def get_metadata(fpath):
    # get election/year and state/name
    elye,stna = fpath.split(sep)[-3:-1]
    # convert to names.csv-friendly form
    year = elye[3:]
    elect = ELECTS[elye[:3]]
    state = STATES[stna[:2]] if elect != "Presidential" else STATES[stna[2:4]]
    # get district
    if elect == 'House':
        state += ' ' + stna[2:4].lstrip('0')
        name = stna[5:]
    elif elect == 'Presidential':
        name = stna[5:]
    else:
        name = stna[3:]

    return elect,year,state,name

def build_context(df):
    dem = df.iloc[0]['D'].split(',')
    rep = df.iloc[0]['R'].split(',')
    thi = df.iloc[0]['T'].split(',')

    if dem != '' and rep != '':
        context = list(filter(None,dem+rep))
    else:
        # only retain first third-party candidate
        context = list(filter(None,dem+rep+thi[0]))

    return context

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('vid_dir',metavar='vid-dir',
                        help='Path to video file directory for transcription')
    parser.add_argument('-up','--use-punct',action='store_true',default=False,
                        help='Enables punctuation annotation for the transcript')

    return parser.parse_args()

def main():
    # get CL arguments
    args = parse_arguments()
    vid_dir = args.vid_dir
    use_punct = args.use_punct

    # get video paths
    fpaths = [join(root,fname) for root,fold,fnames in os.walk(vid_dir)
                                   for fname in fnames
                                       if fname.endswith('.mp4')]
    n_vids = len(fpaths)

    # open names file, leave empty cells as empty strings
    names = pd.read_csv(NAMES,keep_default_na=False)

    # output directory for transcripts (in root of vid_dir)
    if not exists(join(vid_dir,'transcripts')):
        os.mkdir(join(vid_dir,'transcripts'))
        
    # punctuation list (remove comma and add space)
    punct = string.punctuation.replace(',','') + ' '
    # translation table
    tt = str.maketrans(dict.fromkeys(punct))

    # debug file
    with open(join(vid_dir,'log.txt'),'w') as lf:    
        # transcribe
        for i,fpath in enumerate(fpaths):
            print('Transcribing video %d of %d... ' % (i+1,n_vids),end='',flush=True)
            s = default_timer()
            
            # video name
            cur_name = splitext(basename(fpath))[0]
            # election metadata
            elect,year,state,cand = get_metadata(fpath)
            # transcript filename
            tpath = join(vid_dir,'transcripts',cur_name + '.txt')
            
            # check if video already transcribed
            if exists(tpath):
                print('Transcription already exists')
                continue
    
            # get context
            # remove punctuation from names when searching
            sub = names[(names.election == elect) & 
                        (names.year == int(year)) &
                        (names.state == state) & 
                        ((names.D.str.translate(tt).str.contains(cand,case=False)) |
                         (names.R.str.translate(tt).str.contains(cand,case=False)) | 
                         (names['T'].str.translate(tt).str.contains(cand,case=False))
                        )]
            try:
                phrases = build_context(sub)
            except IndexError:
                print('Entry not found for %s in the %s %s election in %s' % (cand,year,elect,state),file=lf)
                print('Failed')
                continue
    
            # transcribe video
            v = Video(fpath)
            try:
                cur_trans = v.transcribe(phrases=phrases,use_punct=use_punct)
            except Exception as e:
                msg = 'Failed on video `%s` with error: `%s`' % (fpath,str(e))
                print(msg,file=lf)
                print('Failed')
                continue
            with open(tpath,'wb') as tf:
                    tf.write(cur_trans.encode('utf-8'))
            print('Done in %4.1f seconds!' % (default_timer()-s))

if __name__ == '__main__':
    main()