from __future__ import annotations

import ast
import operator
from decimal import (
    Decimal,
    DivisionByZero,
    InvalidOperation,
)

from pydantic import Field

from app.schemas.tool import (
    ToolExecutionContext,
    ToolInputModel,
)
from app.tools.base import BaseTool
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.exceptions import (
    ToolExecutionError,
)


MAX_EXPRESSION_LENGTH = 200
MAX_AST_NODES = 50
MAX_ABSOLUTE_RESULT = Decimal("1e100")
MAX_EXPONENT = 12


class CalculatorInput(ToolInputModel):
    expression: str = Field(
        min_length=1,
        max_length=MAX_EXPRESSION_LENGTH,
        description=(
            "A mathematical expression using numbers, "
            "parentheses and supported arithmetic operators."
        ),
    )


class CalculatorTool(
    BaseTool[CalculatorInput]
):
    name = "calculator"

    description = (
        "Safely evaluate basic arithmetic expressions "
        "without executing arbitrary Python code."
    )

    risk_level = ToolRiskLevel.LOW

    permissions = (
        ToolPermission.NONE,
    )

    requires_approval = False

    input_model = CalculatorInput

    async def execute(
        self,
        *,
        arguments: CalculatorInput,
        context: ToolExecutionContext,
    ):
        del context

        try:
            result = _evaluate_expression(
                arguments.expression
            )
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(
                "The calculator could not evaluate "
                "the expression safely."
            ) from exc

        return {
            "expression": arguments.expression,
            "result": _format_decimal(
                result
            ),
        }


def _evaluate_expression(
    expression: str,
) -> Decimal:
    expression = expression.strip()

    if not expression:
        raise ToolExecutionError(
            "Expression cannot be empty."
        )

    try:
        tree = ast.parse(
            expression,
            mode="eval",
        )
    except SyntaxError as exc:
        raise ToolExecutionError(
            "Invalid mathematical expression."
        ) from exc

    nodes = list(
        ast.walk(tree)
    )

    if len(nodes) > MAX_AST_NODES:
        raise ToolExecutionError(
            "Expression is too complex."
        )

    result = _evaluate_node(
        tree.body
    )

    _ensure_result_is_safe(
        result
    )

    return result


def _evaluate_node(
    node: ast.AST,
) -> Decimal:
    if isinstance(
        node,
        ast.Constant,
    ):
        if isinstance(
            node.value,
            bool,
        ):
            raise ToolExecutionError(
                "Boolean values are not supported."
            )

        if isinstance(
            node.value,
            (int, float),
        ):
            return Decimal(
                str(node.value)
            )

        raise ToolExecutionError(
            "Only numeric values are supported."
        )

    if isinstance(
        node,
        ast.UnaryOp,
    ):
        operand = _evaluate_node(
            node.operand
        )

        if isinstance(
            node.op,
            ast.UAdd,
        ):
            return operand

        if isinstance(
            node.op,
            ast.USub,
        ):
            return -operand

        raise ToolExecutionError(
            "Unsupported unary operator."
        )

    if isinstance(
        node,
        ast.BinOp,
    ):
        left = _evaluate_node(
            node.left
        )

        right = _evaluate_node(
            node.right
        )

        result = _apply_operator(
            node.op,
            left,
            right,
        )

        _ensure_result_is_safe(
            result
        )

        return result

    raise ToolExecutionError(
        "Expression contains an unsupported operation."
    )


def _apply_operator(
    operation: ast.operator,
    left: Decimal,
    right: Decimal,
) -> Decimal:
    try:
        if isinstance(
            operation,
            ast.Add,
        ):
            return operator.add(
                left,
                right,
            )

        if isinstance(
            operation,
            ast.Sub,
        ):
            return operator.sub(
                left,
                right,
            )

        if isinstance(
            operation,
            ast.Mult,
        ):
            return operator.mul(
                left,
                right,
            )

        if isinstance(
            operation,
            ast.Div,
        ):
            if right == 0:
                raise ToolExecutionError(
                    "Division by zero is not allowed."
                )

            return operator.truediv(
                left,
                right,
            )

        if isinstance(
            operation,
            ast.FloorDiv,
        ):
            if right == 0:
                raise ToolExecutionError(
                    "Division by zero is not allowed."
                )

            return left // right

        if isinstance(
            operation,
            ast.Mod,
        ):
            if right == 0:
                raise ToolExecutionError(
                    "Modulo by zero is not allowed."
                )

            return left % right

        if isinstance(
            operation,
            ast.Pow,
        ):
            return _safe_power(
                left,
                right,
            )

    except (
        DivisionByZero,
        InvalidOperation,
        OverflowError,
    ) as exc:
        raise ToolExecutionError(
            "The mathematical operation is invalid."
        ) from exc

    raise ToolExecutionError(
        "Unsupported arithmetic operator."
    )


def _safe_power(
    base: Decimal,
    exponent: Decimal,
) -> Decimal:
    if exponent != exponent.to_integral_value():
        raise ToolExecutionError(
            "Only integer exponents are supported."
        )

    exponent_int = int(
        exponent
    )

    if abs(
        exponent_int
    ) > MAX_EXPONENT:
        raise ToolExecutionError(
            f"Exponent magnitude cannot exceed "
            f"{MAX_EXPONENT}."
        )

    if (
        base == 0
        and exponent_int < 0
    ):
        raise ToolExecutionError(
            "Zero cannot be raised to "
            "a negative power."
        )

    try:
        return base ** exponent_int
    except (
        DivisionByZero,
        InvalidOperation,
        OverflowError,
    ) as exc:
        raise ToolExecutionError(
            "Power operation is invalid."
        ) from exc


def _ensure_result_is_safe(
    value: Decimal,
) -> None:
    if not value.is_finite():
        raise ToolExecutionError(
            "Result must be a finite number."
        )

    if abs(
        value
    ) > MAX_ABSOLUTE_RESULT:
        raise ToolExecutionError(
            "Result is too large."
        )


def _format_decimal(
    value: Decimal,
) -> str:
    if value == value.to_integral_value():
        return str(
            value.quantize(
                Decimal("1")
            )
        )

    formatted = format(
        value.normalize(),
        "f",
    )

    return formatted.rstrip(
        "0"
    ).rstrip(
        "."
    )