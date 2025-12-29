"""
Interview History Tracker - Singleton service for tracking interviews and ensuring fair distribution.
Stores interview history and calculates workload balance across Solution Architects.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import pytz


class InterviewTracker:
    """
    Singleton service for tracking interview history and calculating fair distribution.
    In production, this would connect to Unity Catalog or a database.
    For now, uses local JSON file for persistence.
    """
    
    _instance = None
    _interviews: List[Dict] = []
    _sa_registry: Dict[str, Dict] = {}
    
    # Data file path
    DATA_FILE = Path("interview_data.json")
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_data()
        return cls._instance
    
    def _load_data(self) -> None:
        """Load interview data from file."""
        if self.DATA_FILE.exists():
            try:
                with open(self.DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self._interviews = data.get('interviews', [])
                    self._sa_registry = data.get('sa_registry', {})
            except Exception as e:
                print(f"Error loading interview data: {e}")
                self._interviews = []
                self._sa_registry = {}
        else:
            self._interviews = []
            self._sa_registry = self._get_default_sa_registry()
            self._save_data()
    
    def _save_data(self) -> None:
        """Save interview data to file."""
        try:
            with open(self.DATA_FILE, 'w') as f:
                json.dump({
                    'interviews': self._interviews,
                    'sa_registry': self._sa_registry
                }, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving interview data: {e}")
    
    def _get_default_sa_registry(self) -> Dict[str, Dict]:
        """Get default SA registry. In production, this would come from HR system."""
        return {
            "sa1": {
                "id": "sa1",
                "name": "Alex Chen",
                "email": "alex.chen@company.com",
                "calendar_id": "alex.chen@company.com",
                "specialty": "Data Engineering",
                "active": True,
                "max_interviews_per_week": 5
            },
            "sa2": {
                "id": "sa2",
                "name": "Jordan Rivera",
                "email": "jordan.rivera@company.com",
                "calendar_id": "jordan.rivera@company.com",
                "specialty": "ML/AI",
                "active": True,
                "max_interviews_per_week": 5
            },
            "sa3": {
                "id": "sa3",
                "name": "Sam Taylor",
                "email": "sam.taylor@company.com",
                "calendar_id": "sam.taylor@company.com",
                "specialty": "Platform",
                "active": True,
                "max_interviews_per_week": 5
            },
            "sa4": {
                "id": "sa4",
                "name": "Morgan Lee",
                "email": "morgan.lee@company.com",
                "calendar_id": "morgan.lee@company.com",
                "specialty": "Data Science",
                "active": True,
                "max_interviews_per_week": 5
            },
            "sa5": {
                "id": "sa5",
                "name": "Casey Kim",
                "email": "casey.kim@company.com",
                "calendar_id": "casey.kim@company.com",
                "specialty": "Cloud Architecture",
                "active": True,
                "max_interviews_per_week": 5
            },
        }
    
    # ==================== SA Registry Methods ====================
    
    def get_all_sas(self, active_only: bool = True) -> List[Dict]:
        """Get all Solution Architects."""
        sas = list(self._sa_registry.values())
        if active_only:
            sas = [sa for sa in sas if sa.get('active', True)]
        return sas
    
    def get_sa(self, sa_id: str) -> Optional[Dict]:
        """Get a specific SA by ID."""
        return self._sa_registry.get(sa_id)
    
    def get_sa_calendar_ids(self, active_only: bool = True) -> List[str]:
        """Get calendar IDs for all SAs."""
        sas = self.get_all_sas(active_only=active_only)
        return [sa['calendar_id'] for sa in sas if sa.get('calendar_id')]
    
    # ==================== Interview Tracking Methods ====================
    
    def add_interview(
        self,
        candidate_name: str,
        candidate_email: str,
        interview_type: str,
        scheduled_time: str,
        duration_minutes: int,
        assigned_sa_id: str,
        notes: str = ""
    ) -> Dict:
        """
        Record a new scheduled interview.
        
        Returns:
            The created interview record
        """
        interview = {
            "id": f"int_{len(self._interviews)+1}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "interview_type": interview_type,
            "scheduled_time": scheduled_time,
            "duration_minutes": duration_minutes,
            "assigned_sa_id": assigned_sa_id,
            "assigned_sa_name": self._sa_registry.get(assigned_sa_id, {}).get('name', 'Unknown'),
            "status": "scheduled",
            "created_at": datetime.now(pytz.UTC).isoformat(),
            "notes": notes
        }
        
        self._interviews.append(interview)
        self._save_data()
        return interview
    
    def get_interviews(
        self,
        since_days: int = 21,  # Default: last 3 weeks
        sa_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get interviews within a time period.
        
        Args:
            since_days: Look back this many days (default 21 = 3 weeks)
            sa_id: Filter by SA ID
            status: Filter by status
            
        Returns:
            List of matching interviews
        """
        cutoff = datetime.now(pytz.UTC) - timedelta(days=since_days)
        
        filtered = []
        for interview in self._interviews:
            # Parse created_at
            try:
                created = datetime.fromisoformat(interview['created_at'].replace('Z', '+00:00'))
                if created < cutoff:
                    continue
            except (KeyError, ValueError):
                continue
            
            # Apply filters
            if sa_id and interview.get('assigned_sa_id') != sa_id:
                continue
            if status and interview.get('status') != status:
                continue
            
            filtered.append(interview)
        
        return filtered
    
    def get_upcoming_interviews(self) -> List[Dict]:
        """Get all upcoming (future) interviews."""
        now = datetime.now(pytz.UTC)
        
        upcoming = []
        for interview in self._interviews:
            try:
                scheduled = datetime.fromisoformat(interview['scheduled_time'].replace('Z', '+00:00'))
                if scheduled > now and interview.get('status') == 'scheduled':
                    upcoming.append(interview)
            except (KeyError, ValueError):
                continue
        
        # Sort by scheduled time
        upcoming.sort(key=lambda x: x['scheduled_time'])
        return upcoming
    
    # ==================== Fair Distribution Methods ====================
    
    def get_interview_counts(self, since_days: int = 21) -> Dict[str, int]:
        """
        Get interview count per SA for the specified period.
        
        Args:
            since_days: Look back period (default 21 = 3 weeks)
            
        Returns:
            Dict mapping SA ID to interview count
        """
        interviews = self.get_interviews(since_days=since_days)
        
        counts = defaultdict(int)
        # Initialize all active SAs with 0
        for sa in self.get_all_sas():
            counts[sa['id']] = 0
        
        # Count interviews
        for interview in interviews:
            sa_id = interview.get('assigned_sa_id')
            if sa_id:
                counts[sa_id] += 1
        
        return dict(counts)
    
    def get_workload_stats(self, since_days: int = 21) -> Dict[str, Dict]:
        """
        Get detailed workload statistics per SA.
        
        Returns:
            Dict with SA stats including count, percentage, and recommendation score
        """
        counts = self.get_interview_counts(since_days=since_days)
        total = sum(counts.values())
        
        stats = {}
        for sa in self.get_all_sas():
            sa_id = sa['id']
            count = counts.get(sa_id, 0)
            
            # Calculate fair share (what they should have done)
            num_active_sas = len(self.get_all_sas())
            fair_share = total / num_active_sas if num_active_sas > 0 else 0
            
            # Deviation from fair share (negative = under-utilized)
            deviation = count - fair_share
            
            # Priority score: lower count = higher priority for next assignment
            # Also factor in max interviews per week limit
            max_per_week = sa.get('max_interviews_per_week', 5)
            weekly_count = counts.get(sa_id, 0) * (7 / since_days) if since_days > 0 else 0
            capacity_used = weekly_count / max_per_week if max_per_week > 0 else 1
            
            stats[sa_id] = {
                "sa_id": sa_id,
                "sa_name": sa['name'],
                "specialty": sa['specialty'],
                "interview_count": count,
                "fair_share": round(fair_share, 1),
                "deviation": round(deviation, 1),
                "capacity_used_pct": round(capacity_used * 100, 1),
                "priority_score": round(-deviation + (1 - capacity_used) * 2, 2)  # Higher = more priority
            }
        
        return stats
    
    def rank_sas_for_assignment(
        self,
        available_sa_ids: List[str],
        interview_type: Optional[str] = None,
        since_days: int = 21
    ) -> List[Dict]:
        """
        Rank available SAs by priority for the next assignment.
        Considers:
        1. Interview count in the period (fewer = higher priority)
        2. Specialty match if interview_type provided
        3. Capacity limits
        
        Args:
            available_sa_ids: List of SA IDs who are available for the time slot
            interview_type: Optional interview type for specialty matching
            since_days: Look back period for fairness calculation
            
        Returns:
            Sorted list of SA dicts with ranking info, best candidate first
        """
        stats = self.get_workload_stats(since_days=since_days)
        
        # Interview type to specialty mapping
        type_specialty_map = {
            "tech_screen": None,  # Any specialty
            "system_design": ["Platform", "Cloud Architecture"],
            "coding": ["Data Engineering", "Platform"],
            "architecture": ["Cloud Architecture", "Platform"],
            "ml_ai": ["ML/AI", "Data Science"],
            "data": ["Data Engineering", "Data Science"],
        }
        
        preferred_specialties = type_specialty_map.get(interview_type, [])
        
        ranked = []
        for sa_id in available_sa_ids:
            if sa_id not in stats:
                continue
            
            sa_stats = stats[sa_id]
            sa_info = self.get_sa(sa_id)
            
            # Base priority score
            score = sa_stats['priority_score']
            
            # Specialty bonus
            if preferred_specialties and sa_info:
                if sa_info.get('specialty') in preferred_specialties:
                    score += 1.5  # Bonus for specialty match
            
            ranked.append({
                **sa_stats,
                "final_score": round(score, 2),
                "specialty_match": sa_info.get('specialty') in preferred_specialties if preferred_specialties else True
            })
        
        # Sort by final score (highest first)
        ranked.sort(key=lambda x: x['final_score'], reverse=True)
        return ranked
    
    def get_best_sa_for_slot(
        self,
        available_sa_ids: List[str],
        interview_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Get the best SA to assign for an interview slot.
        
        Args:
            available_sa_ids: SAs available for the time slot
            interview_type: Type of interview for specialty matching
            
        Returns:
            SA ID of the best candidate, or None if no one available
        """
        if not available_sa_ids:
            return None
        
        ranked = self.rank_sas_for_assignment(available_sa_ids, interview_type)
        return ranked[0]['sa_id'] if ranked else None


# Singleton getter
def get_interview_tracker() -> InterviewTracker:
    """Get the singleton InterviewTracker instance."""
    return InterviewTracker()

