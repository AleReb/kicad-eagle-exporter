# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
import pcbnew as p

def vec(x,y):
    return p.VECTOR2I(p.FromMM(x),p.FromMM(y))


def demo(directory):
    b = p.BOARD()
    net = p.NETINFO_ITEM(b,"GND")
    b.Add(net)
    for points in [[(10,10),(40,10),(40,30),(10,30)],
                   [(33,23),(36,23),(36,26),(33,26)]]:
        for a,z in zip(points,points[1:]+points[:1]):
            shape=p.PCB_SHAPE(b)
            shape.SetShape(p.SHAPE_T_SEGMENT)
            shape.SetStart(vec(*a)); shape.SetEnd(vec(*z))
            shape.SetWidth(p.FromMM(.05)); shape.SetLayer(p.Edge_Cuts)
            b.Add(shape)
    fp=p.FOOTPRINT(b); fp.SetReference("J1"); b.Add(fp)
    for number,x,y,shape,size,drill,layer in [
        (1,15,15,p.PAD_SHAPE_CIRCLE,(2.6,2.6),1.0,p.F_Cu),
        (2,20,15,p.PAD_SHAPE_RECT,(3,2),0,p.F_Cu),
        (3,25,15,p.PAD_SHAPE_RECT,(3,2),0,p.F_Cu),
        (4,27,25,p.PAD_SHAPE_RECT,(3,2),0,p.B_Cu),
        (5,13,26,p.PAD_SHAPE_CIRCLE,(1.2,1.2),1.2,p.F_Cu)]:
        pad=p.PAD(fp); pad.SetNumber(str(number)); pad.SetPosition(vec(x,y))
        pad.SetSize(vec(*size)); pad.SetShape(shape)
        if drill:
            pad.SetAttribute(p.PAD_ATTRIB_NPTH if number==5 else p.PAD_ATTRIB_PTH)
            pad.SetDrillSize(vec(drill,drill)); pad.SetLayerSet(p.LSET.AllCuMask())
        else:
            pad.SetAttribute(p.PAD_ATTRIB_SMD)
            layers=p.LSET(); layers.AddLayer(layer); pad.SetLayerSet(layers)
        if number==3:
            pad.SetOrientationDegrees(30)
        if number!=5: pad.SetNet(net)
        fp.Add(pad)
    for a,z,layer in [((15,15),(20,15),p.F_Cu),((20,15),(25,15),p.F_Cu),
                       ((25,15),(29,19),p.F_Cu),((29,19),(27,25),p.B_Cu)]:
        t=p.PCB_TRACK(b); t.SetStart(vec(*a)); t.SetEnd(vec(*z))
        t.SetWidth(p.FromMM(.65)); t.SetLayer(layer); t.SetNet(net); b.Add(t)
    arc=p.PCB_ARC(b); arc.SetStart(vec(15,21)); arc.SetMid(vec(18,24)); arc.SetEnd(vec(21,21))
    arc.SetWidth(p.FromMM(.5)); arc.SetLayer(p.F_Cu); arc.SetNet(net); b.Add(arc)
    via=p.PCB_VIA(b); via.SetPosition(vec(29,19)); via.SetWidth(p.FromMM(1.6))
    via.SetDrill(p.FromMM(.8)); via.SetViaType(p.VIATYPE_THROUGH); via.SetNet(net); b.Add(via)
    p.SaveBoard(str(directory/"prueba_kicad10.kicad_pcb"),b)
    return b

