"""Exports a YOLOv5 *.pt model to ONNX and TorchScript formats

Usage:
    $ export PYTHONPATH="$PWD" && python models/export_onnx.py --weights ./weights/yolov5s.pt --img 640 --batch 1
"""

import argparse
import sys
import time

sys.path.append('./')  # to run '$ python *.py' files in subdirectories

import torch
import torch.nn as nn

import models
from models.experimental import attempt_load
from utils.activations import Hardswish, SiLU
from utils.general import set_logging, check_img_size

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', type=str, default='./yolov5s.pt', help='weights path')  # from yolov5/models/
    parser.add_argument('--img-size', nargs='+', type=int, default=[640, 640], help='image size')  # height, width
    parser.add_argument('--batch-size', type=int, default=1, help='batch size')
    opt = parser.parse_args()
    opt.img_size *= 2 if len(opt.img_size) == 1 else 1  # expand
    print(opt)
    set_logging()
    t = time.time()

    # Load PyTorch model
    model = attempt_load(opt.weights, map_location=torch.device('cpu'))  # load FP32 model
    labels = model.names

    # Checks
    gs = int(max(model.stride))  # grid size (max stride)
    opt.img_size = [check_img_size(x, gs) for x in opt.img_size]  # verify img_size are gs-multiples

    # Input
    img = torch.zeros(opt.batch_size, 3, *opt.img_size)  # image size(1,3,320,192) iDetection

    # Update model
    for k, m in model.named_modules():
        m._non_persistent_buffers_set = set()  # pytorch 1.6.0 compatibility
        if isinstance(m, models.common.Conv):  # assign export-friendly activations
            if isinstance(m.act, nn.Hardswish):
                m.act = Hardswish()
            elif isinstance(m.act, nn.SiLU):
                m.act = SiLU()
        # elif isinstance(m, models.yolo.Detect):
        #     m.forward = m.forward_export  # assign forward (optional)
    model.model[-1].export = True  # set Detect() layer export=True
    y = model(img)  # dry run

    # ONNX export
    try:
        import onnx
        from onnxsim import simplify

        print('\nStarting ONNX export with onnx %s...' % onnx.__version__)
        f = opt.weights.replace('.pt', '.onnx')  # filename
        torch.onnx.export(model, img, f, verbose=False, opset_version=12, input_names=['images'],
                          output_names=['classes', 'boxes'] if y is None else ['output'])

        # Checks
        onnx_model = onnx.load(f)  # load onnx model
        onnx.checker.check_model(onnx_model)  # check onnx model
        print(onnx.helper.printable_graph(onnx_model.graph))  # print a human readable model

        sim_f = opt.weights.replace('.pt', '.sim.onnx')  # filename
        model_simp, check = simplify(onnx_model)
        assert check, "Simplified ONNX model could not be validated"
        onnx.save(model_simp, sim_f)

        # print(onnx.helper.printable_graph(model_simp.graph))  # print a human readable model
        print('ONNX export success, saved as %s' % f)
    except Exception as e:
        print('ONNX export failure: %s' % e)

    # Finish
    print('\nExport complete (%.2fs). Visualize with https://github.com/lutzroeder/netron.' % (time.time() - t))
