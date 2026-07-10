"""A20 语义分割深度学习模型

使用PyTorch U-Net进行像素级语义分割:
    1. 支持GPU推理(CUDA)
    2. U-Net架构(编码器-解码器+跳跃连接)
    3. 支持预训练权重加载
    4. 分块推理(大影像分块处理)
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A20SemanticSegmentation(Algorithm):
    """A20 语义分割深度学习模型"""

    @staticmethod
    def name() -> str:
        return "a20_semantic_segmentation"

    @staticmethod
    def display_name() -> str:
        return "A20 语义分割深度学习模型"

    @staticmethod
    def group() -> str:
        return "M4 DLG提取"

    @staticmethod
    def group_id() -> str:
        return "m4"

    @staticmethod
    def short_help() -> str:
        return "PyTorch U-Net语义分割,GPU加速推理"

    @staticmethod
    def can_execute() -> bool:
        try:
            import torch
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: DOM影像路径 (str, .tif)
        """
        dom_path = input_data
        if not dom_path or not os.path.exists(dom_path):
            return AlgoResult(status=1, message=f"DOM文件无效: {dom_path}")

        output_path = context.param("output_path",
                                     dom_path.replace(".tif", "_segmentation.tif"))
        model_path = context.param("model_path", "")
        n_classes = context.param("n_classes", 5)
        tile_size = context.param("tile_size", 512)

        feedback.push_info(f"输入: {dom_path}")
        feedback.push_info(f"模型: {model_path or '未指定(使用随机初始化)'}")

        import torch
        import torch.nn as nn
        import rasterio

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        feedback.push_info(f"设备: {device}")

        # 1. U-Net 模型定义
        class UNet(nn.Module):
            def __init__(self, in_channels=3, n_classes=5):
                super().__init__()

                def conv_block(in_ch, out_ch):
                    return nn.Sequential(
                        nn.Conv2d(in_ch, out_ch, 3, padding=1),
                        nn.ReLU(inplace=True),
                        nn.Conv2d(out_ch, out_ch, 3, padding=1),
                        nn.ReLU(inplace=True)
                    )

                self.enc1 = conv_block(in_channels, 64)
                self.enc2 = conv_block(64, 128)
                self.enc3 = conv_block(128, 256)
                self.enc4 = conv_block(256, 512)
                self.bottleneck = conv_block(512, 1024)

                self.upconv4 = nn.ConvTranspose2d(1024, 512, 2, stride=2)
                self.dec4 = conv_block(1024, 512)
                self.upconv3 = nn.ConvTranspose2d(512, 256, 2, stride=2)
                self.dec3 = conv_block(512, 256)
                self.upconv2 = nn.ConvTranspose2d(256, 128, 2, stride=2)
                self.dec2 = conv_block(256, 128)
                self.upconv1 = nn.ConvTranspose2d(128, 64, 2, stride=2)
                self.dec1 = conv_block(128, 64)

                self.out_conv = nn.Conv2d(64, n_classes, 1)
                self.pool = nn.MaxPool2d(2)

            def forward(self, x):
                e1 = self.enc1(x)
                e2 = self.enc2(self.pool(e1))
                e3 = self.enc3(self.pool(e2))
                e4 = self.enc4(self.pool(e3))
                b = self.bottleneck(self.pool(e4))

                d4 = self.upconv4(b)
                d4 = self.dec4(torch.cat([d4, e4], dim=1))
                d3 = self.upconv3(d4)
                d3 = self.dec3(torch.cat([d3, e3], dim=1))
                d2 = self.upconv2(d3)
                d2 = self.dec2(torch.cat([d2, e2], dim=1))
                d1 = self.upconv1(d2)
                d1 = self.dec1(torch.cat([d1, e1], dim=1))

                return self.out_conv(d1)

        # 2. 加载模型
        feedback.set_progress_text("加载模型...")
        model = UNet(in_channels=3, n_classes=n_classes).to(device)
        if model_path and os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path, map_location=device))
            feedback.push_info("预训练权重加载完成")
        else:
            feedback.push_warning("未加载预训练权重,输出为随机推理结果")
        model.eval()
        feedback.set_progress(30)

        # 3. 读取影像
        feedback.set_progress_text("读取影像...")
        with rasterio.open(dom_path) as src:
            dom = src.read()
            profile = src.profile

        bands, rows, cols = dom.shape
        if bands < 3:
            return AlgoResult(status=1, message="影像至少需要3波段")

        rgb = np.transpose(dom[:3], (1, 2, 0)).astype(np.float32) / 255.0
        feedback.set_progress(40)

        # 4. 分块推理
        feedback.set_progress_text(f"分块推理 (tile={tile_size})...")
        result = np.zeros((rows, cols), dtype=np.uint8)

        import torchvision.transforms.functional as TF

        tiles_y = (rows + tile_size - 1) // tile_size
        tiles_x = (cols + tile_size - 1) // tile_size
        total_tiles = tiles_y * tiles_x

        with torch.no_grad():
            for ty in range(tiles_y):
                for tx in range(tiles_x):
                    y1 = ty * tile_size
                    y2 = min(y1 + tile_size, rows)
                    x1 = tx * tile_size
                    x2 = min(x1 + tile_size, cols)

                    tile = rgb[y1:y2, x1:x2]
                    # padding 到 tile_size
                    pad_h = tile_size - (y2 - y1)
                    pad_w = tile_size - (x2 - x1)
                    if pad_h > 0 or pad_w > 0:
                        tile = np.pad(tile, ((0, pad_h), (0, pad_w), (0, 0)),
                                      mode='reflect')

                    tensor = TF.to_tensor(tile).unsqueeze(0).to(device)

                    output = model(tensor)
                    pred = torch.argmax(output, dim=1).squeeze(0).cpu().numpy()

                    # 去除 padding
                    result[y1:y2, x1:x2] = pred[:y2-y1, :x2-x1]

                    done = ty * tiles_x + tx + 1
                    feedback.set_progress(40 + int(done / total_tiles * 55))

        # 5. 保存
        feedback.set_progress_text("保存分割结果...")
        out_profile = profile.copy()
        out_profile.update(dtype='uint8', count=1)
        with rasterio.open(output_path, 'w', **out_profile) as dst:
            dst.write(result, 1)

        feedback.set_progress(100)
        feedback.push_info(f"分割完成: {output_path}")

        return AlgoResult(
            status=0,
            message=f"语义分割完成 (device={device}, tiles={total_tiles})",
            outputs=[output_path],
            metadata={
                "output_path": output_path,
                "device": str(device),
                "n_classes": n_classes,
                "tile_size": tile_size,
                "model_loaded": bool(model_path and os.path.exists(model_path)),
            }
        )
