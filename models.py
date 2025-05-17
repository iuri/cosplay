from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class ColumnLabel(Base):
    __tablename__ = 'column_labels'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    responses = relationship("FormResponse", back_populates="column")

class FormResponse(Base):
    __tablename__ = 'form_responses'
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, index=True)  # groups multiple columns into one form submission
    column_id = Column(Integer, ForeignKey('column_labels.id'))
    value = Column(String)
    approved = Column(String, default=None)  # 'approved' | 'disapproved' | None

    column = relationship("ColumnLabel", back_populates="responses")
