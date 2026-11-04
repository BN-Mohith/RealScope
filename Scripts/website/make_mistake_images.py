"""
STEP 6 - draw the pictures used on the Mistakes page.

These are SIMULATED microscope views (made with code, not photographs): a field of
stained onion-like cells with one common slide mistake added to each (air bubble,
overstaining, dust, ...). They are labelled "Simulated view" on the website.
Replace any of them with a real photo: save it as  Data/website/img/mistakes/real/<name>.jpg
(e.g. real/air.jpg) and run build_website.py again - the "Simulated view" tag then disappears.
Names: air over under crystals dust fibres folds thick drying focus light smudge shrink

    python Scripts/website/make_mistake_images.py           (skips if all 13 exist)
    python Scripts/website/make_mistake_images.py --force
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "Data" / "website" / "img" / "mistakes"
NAMES = ["air", "over", "under", "crystals", "dust", "fibres", "folds", "thick", "drying",
         "focus", "light", "smudge", "shrink"]
OUT.mkdir(parents=True, exist_ok=True)
if "--force" not in sys.argv and all((OUT / (n + ".jpg")).exists() for n in NAMES):
    print(f"  mistake pictures already exist -> {OUT}  (use --force to redraw)")
    sys.exit(0)

W,H=720,480
rng=np.random.default_rng(7)
def blur(a,s): return cv2.GaussianBlur(a,(0,0),s) if s>0 else a

def cell_field(seed=1):
    r=np.random.default_rng(seed)
    sx=2.3
    pts=[]
    for gy in np.arange(-40,H+60,62):
        off=r.uniform(0,140)
        for gx in np.arange(-160,W+160,140):
            pts.append((gx+off+r.uniform(-22,22), gy+r.uniform(-10,10)))
    pts=np.array(pts)
    yy,xx=np.mgrid[0:H,0:W]
    P=np.c_[pts[:,0]/sx,pts[:,1]].astype(np.float32)
    best=np.full((H,W),1e9,np.float32); second=np.full((H,W),1e9,np.float32); lab=np.zeros((H,W),np.int32)
    gx=(xx/sx).astype(np.float32); gy=yy.astype(np.float32)
    for k,(px,py) in enumerate(P):
        d=np.sqrt((gx-px)**2+(gy-py)**2)
        closer=d<best
        second=np.where(closer,best,np.minimum(second,d)); lab=np.where(closer,k,lab); best=np.where(closer,d,best)
    gapd=second-best
    wv=r.uniform(0.6,1.0,len(pts))[lab]
    thick=2.2+1.2*blur(r.normal(0,1,(H,W)).astype(np.float32),25)
    wall=np.clip(1-gapd/thick,0,1)**0.8*wv
    nuc=np.zeros((H,W),np.float32); nucl=np.zeros((H,W),np.float32)
    for (px,py) in pts:
        cx=px+r.uniform(-30,30); cy=py+r.uniform(-10,10)
        if not(-20<cx<W+20 and -20<cy<H+20): continue
        a,b=r.uniform(11,15),r.uniform(8,11)
        cv2.ellipse(nuc,(int(cx),int(cy)),(int(a),int(b)),r.uniform(-20,20),0,360,1.0,-1,cv2.LINE_AA)
        for k in range(r.integers(1,3)):
            cv2.circle(nucl,(int(cx+r.uniform(-4,4)),int(cy+r.uniform(-3,3))),int(r.uniform(2,3.5)),1.0,-1,cv2.LINE_AA)
    chrom=0.75+0.35*blur(r.normal(0,1,(H,W)).astype(np.float32),1.2)
    nuc=blur(nuc,1.4)*chrom+blur(nucl,0.8)*0.6
    gran=blur(r.normal(0,1,(H,W)).astype(np.float32),1.0)*0.06+blur(r.normal(0,1,(H,W)).astype(np.float32),8)*0.08
    cyto=np.clip(0.16+gran,0,1)*(1-wall)
    return blur(wall,1.0), np.clip(nuc,0,1.4), cyto

STAIN=np.array([0.55,0.95,0.45])   # absorbance per channel (B,G,R) -> magenta/pink
def render(wall,nuc,cyto,stain=1.0,light=None,bg=(248,244,246)):
    a=(wall*1.1+nuc*1.6+cyto*0.25)*stain
    img=np.zeros((H,W,3),np.float32)
    for c in range(3): img[...,c]=bg[c]*np.exp(-a*STAIN[c]*1.4)
    if light is None:
        yy,xx=np.mgrid[0:H,0:W]; d=((xx-W/2)/(W*0.75))**2+((yy-H/2)/(H*0.75))**2
        light=1-0.28*d
    img*=light[...,None]
    img+=np.random.default_rng(3).normal(0,2.2,img.shape)
    return np.clip(img,0,255)

def save(name,img):
    cv2.imwrite(str(OUT/(name+'.jpg')),img.astype(np.uint8),[cv2.IMWRITE_JPEG_QUALITY,88])

wall,nuc,cyto=cell_field(1)
base=lambda **k: render(wall,nuc,cyto,**k)

# 1 air bubbles
img=base()
for (cx,cy,R) in [(300,230,95),(560,120,40),(150,390,28)]:
    yy,xx=np.mgrid[0:H,0:W]; d=np.sqrt((xx-cx)**2+(yy-cy)**2)
    inside=d<R
    ring=np.exp(-((d-R*0.93)/(R*0.07))**2)
    inner=np.exp(-((d-R*0.62)/(R*0.05))**2)*0.25
    img[inside]=img[inside]*0.25+np.array([250,250,250])*0.75   # bright empty centre
    dark=np.clip(ring*1.0,0,1)
    img=img*(1-dark[...,None])+np.array([35,30,32])*dark[...,None]
    img=img*(1-inner[...,None])+np.array([120,118,118])*inner[...,None]
save('air',img)
# 2 overstain
save('over',render(wall,nuc,cyto*3.2,stain=2.6))
# 3 understain
save('under',render(wall,nuc,cyto,stain=0.16))
# 4 crystals
img=base(); r=np.random.default_rng(11); m=np.zeros((H,W),np.float32)
for i in range(70):
    x,y=r.integers(0,W),r.integers(0,H)
    if r.random()<0.5:
        L=r.uniform(8,26); t=r.uniform(0,np.pi)
        cv2.line(m,(int(x),int(y)),(int(x+L*np.cos(t)),int(y+L*np.sin(t))),1.0,int(r.integers(1,3)),cv2.LINE_AA)
    else:
        s=r.uniform(2,6); pts=np.array([[x+s*np.cos(a),y+s*np.sin(a)] for a in np.linspace(0,2*np.pi,5)[:-1]+r.uniform(0,1)],np.int32)
        cv2.fillPoly(m,[pts],1.0,cv2.LINE_AA)
m=blur(m,0.5)
img=img*(1-m[...,None]*0.9)+np.array([70,20,60])*(m[...,None]*0.9)
save('crystals',img)
# 5 dust
img=base(); r=np.random.default_rng(5)
for i in range(16):
    m=np.zeros((H,W),np.float32); x,y=r.integers(20,W-20),r.integers(20,H-20); s=r.uniform(3,14)
    pts=np.array([[x+s*r.uniform(0.5,1.3)*np.cos(a),y+s*r.uniform(0.5,1.3)*np.sin(a)] for a in np.linspace(0,2*np.pi,9)[:-1]],np.int32)
    cv2.fillPoly(m,[pts],1.0,cv2.LINE_AA); m=blur(m,r.choice([0.6,2.5,5]))
    img=img*(1-m[...,None]*0.85)+np.array([40,45,50])*(m[...,None]*0.85)
save('dust',img)
# 6 fibre
img=base(); m=np.zeros((H,W),np.float32)
t=np.linspace(0,1,400); xs=-20+t*(W+40); ys=380-260*t+40*np.sin(t*7)
cv2.polylines(m,[np.stack([xs,ys],1).astype(np.int32)],False,1.0,13,cv2.LINE_AA)
edge=cv2.Canny((m*255).astype(np.uint8),50,150).astype(np.float32)/255
m=blur(m,2.2); edge=blur(edge,1.3)
img=img*(1-m[...,None]*0.35)+np.array([170,178,186])*(m[...,None]*0.35)
img=img*(1-edge[...,None]*0.7)+np.array([60,62,66])*(edge[...,None]*0.7)
save('fibres',img)
# 7 fold: band of double tissue
w2,n2,c2=cell_field(9)
band=np.zeros((H,W),np.float32); cv2.fillPoly(band,[np.array([[300,0],[400,0],[470,H],[370,H]],np.int32)],1.0); band=blur(band,3)
img=render(wall+band*w2*0.9,nuc+band*n2,cyto+band*0.5)
save('folds',img)
# 8 too thick: two layers, second out of focus
w2,n2,c2=cell_field(4)
img=render(wall+blur(w2,4)*0.8,nuc+blur(n2,4)*0.8,cyto*1.8+c2)
save('thick',img)
# 9 drying: air from right edge with meniscus + crystals
img=base(); yy,xx=np.mgrid[0:H,0:W]
edge_x=520+40*np.sin(yy/55.0)+20*np.sin(yy/17.0)
dry=(xx>edge_x).astype(np.float32); dry=blur(dry,1.2)
img=img*(1-dry[...,None]*0.85)+np.array([252,252,252])*(dry[...,None]*0.85)
men=np.exp(-((xx-edge_x)/5.0)**2)
img=img*(1-men[...,None]*0.85)+np.array([30,30,30])*(men[...,None]*0.85)
r=np.random.default_rng(2); m=np.zeros((H,W),np.float32)
for i in range(45):
    y=int(r.integers(0,H)); x=int(edge_x[y,0]+r.uniform(5,60))
    cv2.circle(m,(x,y),int(r.integers(1,4)),1.0,-1,cv2.LINE_AA)
m=blur(m,0.6); img=img*(1-m[...,None]*0.8)+np.array([90,60,90])*(m[...,None]*0.8)
save('drying',img)
# 10 out of focus: blur with halos
img=base(); b=cv2.GaussianBlur(img,(0,0),5); halo=img-cv2.GaussianBlur(img,(0,0),12)
save('focus',np.clip(b-0.6*halo,0,255))
# 11 lighting: uneven, one side dark + washed out
yy,xx=np.mgrid[0:H,0:W]; light=np.clip(0.25+0.95*(xx/W)**0.6,0,1.15)*(1-0.15*((yy-H/2)/H)**2)
save('light',render(wall,nuc,cyto,stain=0.55,light=light))
# 12 smudge: hazy patch with faint ridges
img=base(); yy,xx=np.mgrid[0:H,0:W]
d=np.sqrt(((xx-380)/1.3)**2+(yy-230)**2); patch=np.exp(-(d/170)**2)
ridges=0.5+0.5*np.sin(d/4.2+3*np.sin(xx/60.0))
haze=patch*(0.45+0.45*ridges)
img=cv2.GaussianBlur(img,(0,0),3)*patch[...,None]*0.6+img*(1-patch[...,None]*0.6)
img=img*(1-haze[...,None]*0.55)+np.array([205,206,200])*(haze[...,None]*0.55)
save('smudge',img)
# 13 shrinkage: dense tissue with clean white crack
r=np.random.default_rng(21); a=np.zeros((H,W),np.float32); e=0.35+0.12*blur(r.normal(0,1,(H,W)).astype(np.float32),6)
for i in range(1400):
    cv2.ellipse(a,(int(r.integers(0,W)),int(r.integers(0,H))),(int(r.uniform(4,7)),int(r.uniform(3,6))),r.uniform(0,180),0,360,1.0,-1,cv2.LINE_AA)
a=blur(a,0.9)
yy,xx=np.mgrid[0:H,0:W]; cx=360+60*np.sin(yy/70.0)+25*np.sin(yy/23.0); width=10+14*(0.5+0.5*np.sin(yy/90.0))
gap=(np.abs(xx-cx)<width).astype(np.float32); gap=blur(gap,1.2)
img=np.zeros((H,W,3),np.float32); bg=(250,246,250)
hem=np.array([0.35,0.75,0.25]); eos=np.array([0.05,0.55,0.12])
for c in range(3): img[...,c]=bg[c]*np.exp(-(a*hem[c]*2.2+e*eos[c]*2.0))
img=img*(1-gap[...,None])+np.array([252,251,252])*gap[...,None]
yy2,xx2=np.mgrid[0:H,0:W]; img*= (1-0.22*(((xx2-W/2)/(W*0.75))**2+((yy2-H/2)/(H*0.75))**2))[...,None]
save('shrink',img+np.random.default_rng(1).normal(0,2,img.shape))
print(f"  13 mistake pictures -> {OUT}")
