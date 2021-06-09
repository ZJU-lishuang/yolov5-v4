#refer to (https://github.com/onnx/onnx-tensorrt/blob/master/docs/faq.md#inputsat0-must-be-an-initializer-or-inputsat0is_weights)
polygraphy surgeon sanitize yolov5s.onnx --fold-constants --output model_folded.onnx
