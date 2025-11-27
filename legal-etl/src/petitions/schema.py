from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


PetitionType = Literal[
    "dava_dilekcesi",
    "cevap_dilekcesi",
    "istinaf",
    "temyiz",
    "idari",
    "suc_duyurusu",
]


class Party(BaseModel):
    role: Literal["davaci", "davali", "davaci_vekili", "davali_vekili", "mukabil"]
    name: str
    address: Optional[str] = None
    tc_id: Optional[str] = Field(default=None, description="TC kimlik no (varsa)")
    representation: Optional[str] = Field(default=None, description="Şirket/kurum ise unvan")


class Evidence(BaseModel):
    label: str
    description: Optional[str] = None
    file_id: Optional[str] = Field(default=None, description="Uygulama içi dosya referansı")


class Fact(BaseModel):
    summary: str
    evidence_refs: List[str] = Field(default_factory=list)


class PetitionInput(BaseModel):
    petition_type: PetitionType
    court: str
    subject: str
    parties: List[Party]
    facts: List[Fact]
    legal_basis: List[str] = Field(default_factory=list)
    requests: List[str]
    evidence: List[Evidence] = Field(default_factory=list)
    decision_reference: Optional[str] = Field(
        default=None, description="İstinaf/temyiz için karar no/tarihi"
    )
    service_date: Optional[date] = Field(default=None, description="Tebliğ tarihi (süre kontrolü)")
    extra_notes: Optional[str] = None

    @field_validator("parties")
    def require_party_roles(cls, v: List[Party]) -> List[Party]:
        roles = [p.role for p in v]
        if "davaci" not in roles and "davaci_vekili" not in roles:
            raise ValueError("En az bir davacı veya davacı vekili tanımlanmalı.")
        return v

    @field_validator("facts")
    def facts_cannot_be_empty(cls, v: List[Fact]) -> List[Fact]:
        if not v:
            raise ValueError("En az bir olgu eklenmeli.")
        return v

    @field_validator("requests")
    def requests_cannot_be_empty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("En az bir talep eklenmeli.")
        return v


class GeneratedSections(BaseModel):
    subject: str
    facts: List[str]
    legal_basis: List[str]
    evidence: List[str]
    requests: List[str]
    tone_notes: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)


class PetitionOutput(BaseModel):
    text: str
    html: str | None = None
    qa_warnings: List[str] = Field(default_factory=list)
    sections: GeneratedSections
