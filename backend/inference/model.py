from torch import nn
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights


def build_model(architecture, num_classes, pretrained):
    if architecture != 'efficientnet_b0':
        raise ValueError(f'Unsupported backbone: {architecture}')
    weights = EfficientNet_B0_Weights.DEFAULT if pretrained else None
    model = efficientnet_b0(weights=weights)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    return model